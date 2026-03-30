"""
Rule-based action and mention extraction.

Extracts:
1. Direct mentions of user (via aliases)
2. Action requests/imperatives directed at user
3. Questions requiring user response

Uses confidence scoring based on:
- Addressability (direct mention of user)
- Imperative verbs
- Question markers
- Deadline/date presence
- Sender importance

Enhancements:
- Lightweight lemmatization for RU/EN verbs (no heavy dependencies)
- Matches verbs by both exact form and lemma
"""

import re
import math
import structlog
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

from digest_core.evidence.lemmatizer import LightweightLemmatizer

logger = structlog.get_logger()


@dataclass
class ExtractedAction:
    """Extracted action or mention."""

    type: str  # "action", "question", "mention"
    who: str  # Who should act (usually "user" for My Actions)
    verb: str  # Action verb or question type
    text: str  # Full text of the action/mention
    due: Optional[str] = None  # Deadline if found
    confidence: float = 0.0  # 0.0-1.0
    evidence_id: str = ""  # Will be set later
    msg_id: str = ""  # Message ID
    start_offset: int = 0  # Start offset in normalized text
    end_offset: int = 0  # End offset in normalized text


class ActionMentionExtractor:
    """Extract actions and mentions from email text."""

    # Russian imperative verbs and action markers
    RU_IMPERATIVE_VERBS = [
        r"\b(сделай(?:те)?|выполни(?:те)?|проверь(?:те)?|отправь(?:те)?|пришли(?:те)?)",
        r"\b(подготовь(?:те)?|согласуй(?:те)?|утверди(?:те)?|одобри(?:те)?)",
        r"\b(посмотри(?:те)?|изучи(?:те)?|рассмотри(?:те)?|оцени(?:те)?)",
        r"\b(ответь(?:те)?|напиши(?:те)?|сообщи(?:те)?|уведоми(?:те)?)",
        r"\b(передай(?:те)?|дай(?:те)?|предоставь(?:те)?|подай(?:те)?)",
        r"\b(исправь(?:те)?|поправь(?:те)?|обнови(?:те)?|измени(?:те)?)",
        r"\b(завершите?|закончите?|доделай(?:те)?|финализируй(?:те)?)",
    ]

    # English imperative verbs and action markers
    EN_IMPERATIVE_VERBS = [
        r"\b(please|could you|can you|would you|will you)",
        r"\b(need you to|want you to|asking you to|request you to)",
        r"\b(make sure|ensure|verify|confirm|check)",
        r"\b(review|approve|sign off|validate|examine)",
        r"\b(send|provide|submit|deliver|share)",
        r"\b(update|fix|correct|change|modify)",
        r"\b(complete|finish|finalize|wrap up)",
        r"\b(prepare|create|draft|develop)",
    ]

    # Russian action requests
    RU_ACTION_MARKERS = [
        r"\b(нужно|необходимо|требуется|надо)\s+",
        r"\b(прошу|прошу вас|прошу тебя)\s+",
        r"\b(можешь|можете|сможешь|сможете)\s+",
        r"\b(давай(?:те)?)\s+",
        r"\b(пожалуйста)\s*[,:]",
    ]

    # English action markers
    EN_ACTION_MARKERS = [
        r"\bneed to\s+",
        r"\bneed\b.{0,40}\bto\b",
        r"\bhave to\s+",
        r"\bmust\s+",
        r"\bshould\s+",
        r"\bplease\s+",
    ]

    # Question markers
    RU_QUESTION_MARKERS = [
        r"\?",  # Question mark
        r"\b(когда|где|как|что|кто|почему|зачем)\b",
        r"\b(можно|возможно|получится)\s+ли\b",
    ]

    EN_QUESTION_MARKERS = [
        r"\?",  # Question mark
        r"\b(what|when|where|how|who|why|which)\b",
        r"\b(can|could|would|will|should|is|are|do|does)\s+",
    ]

    # Date/deadline patterns
    DATE_PATTERNS = [
        r"\b(до|к|не позднее)\s+\d{1,2}[./]\d{1,2}",  # до 15.01
        r"\b(by|until|before)\s+\d{1,2}[./]\d{1,2}",  # by 01/15
        r"\b(сегодня|завтра|послезавтра|вчера)\b",  # today, tomorrow
        r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday)\b",
        r"\b(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)\b",
        r"\b(deadline|дедлайн|срок)\s*:?\s*\d",
        r"\b(eod|end of day|конец дня)\b",
    ]

    def __init__(
        self,
        user_aliases: List[str],
        user_timezone: str = "UTC",
        custom_verbs: Dict[str, str] = None,
    ):
        """
        Initialize ActionMentionExtractor.

        Args:
            user_aliases: List of user email addresses and names to detect mentions
            user_timezone: User timezone for date parsing
            custom_verbs: Optional custom verb lemma dictionary for domain-specific actions
        """
        self.user_aliases = [alias.lower() for alias in user_aliases]
        self.mention_aliases = self._build_mention_aliases(user_aliases)
        self.user_timezone = user_timezone

        # Initialize lemmatizer with custom verbs
        self.lemmatizer = LightweightLemmatizer(custom_verbs=custom_verbs)

        # Build action verb lemma sets for quick lookup
        self._build_action_verb_lemmas()

        # Compile regex patterns for performance
        self._compile_patterns()

    def _build_mention_aliases(self, aliases: List[str]) -> List[str]:
        """Expand aliases with common first-name/local-part variants."""
        expanded: Set[str] = set()

        for alias in aliases:
            alias_lower = alias.lower().strip()
            if not alias_lower:
                continue
            expanded.add(alias_lower)

            if "@" in alias_lower:
                local_part = alias_lower.split("@", 1)[0]
                expanded.add(local_part)
                for part in re.split(r"[._-]+", local_part):
                    if len(part) >= 3:
                        expanded.add(part)

            if " " in alias_lower:
                for part in alias_lower.split():
                    if len(part) >= 3:
                        expanded.add(part)

        return sorted(expanded, key=len, reverse=True)

    def _build_action_verb_lemmas(self):
        """Build sets of action verb lemmas for quick matching."""
        # EN action verbs (base forms)
        self.en_action_verbs = {
            "ask",
            "provide",
            "check",
            "update",
            "confirm",
            "send",
            "review",
            "approve",
            "complete",
            "finish",
            "deliver",
            "submit",
            "prepare",
            "create",
            "schedule",
            "arrange",
            "coordinate",
            "organize",
            "verify",
            "validate",
            "investigate",
            "resolve",
            "fix",
            "implement",
            "discuss",
            "meet",
            "call",
            "contact",
            "inform",
            "notify",
            "remind",
            "follow",
            "escalate",
            "prioritize",
            "decide",
        }

        # RU action verbs (infinitives)
        self.ru_action_verbs = {
            "сделать",
            "проверить",
            "прислать",
            "подтвердить",
            "уточнить",
            "договориться",
            "перенести",
            "собрать",
            "подготовить",
            "отправить",
            "согласовать",
            "обсудить",
            "решить",
            "организовать",
            "ответить",
            "предоставить",
            "дать",
            "взять",
            "написать",
            "позвонить",
            "встретиться",
            "выполнить",
            "утвердить",
            "одобрить",
            "посмотреть",
            "изучить",
            "рассмотреть",
            "оценить",
            "сообщить",
            "уведомить",
            "передать",
            "исправить",
            "поправить",
            "обновить",
            "изменить",
            "завершить",
            "закончить",
            "доделать",
            "финализировать",
        }

    def _compile_patterns(self):
        """Compile all regex patterns."""
        self.ru_imperative_pattern = re.compile("|".join(self.RU_IMPERATIVE_VERBS), re.IGNORECASE)
        self.en_imperative_pattern = re.compile("|".join(self.EN_IMPERATIVE_VERBS), re.IGNORECASE)
        self.ru_action_pattern = re.compile("|".join(self.RU_ACTION_MARKERS), re.IGNORECASE)
        self.en_action_pattern = re.compile("|".join(self.EN_ACTION_MARKERS), re.IGNORECASE)
        self.ru_question_pattern = re.compile("|".join(self.RU_QUESTION_MARKERS), re.IGNORECASE)
        self.en_question_pattern = re.compile("|".join(self.EN_QUESTION_MARKERS), re.IGNORECASE)
        self.date_pattern = re.compile("|".join(self.DATE_PATTERNS), re.IGNORECASE)

    def extract_mentions_actions(
        self, text: str, msg_id: str, sender: str, sender_rank: float = 0.5
    ) -> List[ExtractedAction]:
        """
        Extract actions and mentions from email text.

        Args:
            text: Normalized email body text
            msg_id: Message ID
            sender: Sender email
            sender_rank: Sender importance (0.0-1.0)

        Returns:
            List of ExtractedAction objects
        """
        if not text:
            return []

        actions = []

        # Split into sentences
        sentences = self._split_sentences(text)

        current_offset = 0
        for sentence in sentences:
            # Find sentence in original text
            start_offset = text.find(sentence, current_offset)
            if start_offset == -1:
                start_offset = current_offset
            end_offset = start_offset + len(sentence)
            current_offset = end_offset

            # Check if sentence mentions user
            has_user_mention = self._has_user_mention(sentence)

            # Check for imperative verbs
            imperative_match = self._find_imperative(sentence)

            # Check for action markers
            action_marker_match = self._find_action_marker(sentence)

            # Check for questions
            is_question = self._is_question(sentence)

            # Check for deadline
            deadline = self._extract_deadline(sentence)

            # Skip if no actionable content
            if not (has_user_mention or imperative_match or action_marker_match or is_question):
                continue

            # Determine action type and verb
            action_type = "mention"
            verb = "mentioned"

            if is_question:
                action_type = "question"
                verb = "answer"
            elif imperative_match or action_marker_match:
                action_type = "action"
                verb = imperative_match or action_marker_match or "do"

            # Calculate confidence
            features = {
                "has_user_mention": has_user_mention,
                "has_imperative": bool(imperative_match),
                "has_action_marker": bool(action_marker_match),
                "is_question": is_question,
                "has_deadline": bool(deadline),
                "sender_rank": sender_rank,
            }
            confidence = self._calculate_confidence(features)

            # Create action
            action = ExtractedAction(
                type=action_type,
                who="user",
                verb=verb,
                text=sentence.strip(),
                due=deadline,
                confidence=confidence,
                msg_id=msg_id,
                start_offset=start_offset,
                end_offset=end_offset,
            )

            actions.append(action)

        # Sort by confidence (highest first)
        actions.sort(key=lambda a: a.confidence, reverse=True)

        logger.info(
            "Extracted actions/mentions",
            msg_id=msg_id,
            total_actions=len(actions),
            avg_confidence=(sum(a.confidence for a in actions) / len(actions) if actions else 0),
        )

        return actions

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitter (can be improved with NLP library)
        # Split on: . ! ? followed by space and capital letter, or newline
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])|(?<=[.!?])\n+", text)

        # Filter out very short sentences (< 10 chars)
        sentences = [s for s in sentences if len(s.strip()) >= 10]

        return sentences

    def _has_user_mention(self, text: str) -> bool:
        """Check if text mentions user (via aliases)."""
        text_lower = text.lower()

        for alias in self.mention_aliases:
            if self._match_alias(text_lower, alias):
                return True

        return False

    def _match_alias(self, text_lower: str, alias: str) -> bool:
        """Match alias with simple word-boundary handling and noisy-context skips."""
        if not alias:
            return False

        if any(char in alias for char in "@ "):
            return alias in text_lower

        pattern = re.compile(rf"(?<!\w){re.escape(alias)}(?:'s)?(?!\w)", re.IGNORECASE)
        match = pattern.search(text_lower)
        if not match:
            return False

        suffix = text_lower[match.end() :].lstrip()
        if suffix.startswith("team") or suffix.startswith("group") or suffix.startswith("dept"):
            return False

        return True

    def _find_imperative(self, text: str) -> Optional[str]:
        """
        Find imperative verb in text.

        Strategy:
        1. First check regex patterns (exact match)
        2. If not found, tokenize and check lemmas
        """
        # Strategy 1: Check regex patterns (exact match)
        match = self.ru_imperative_pattern.search(text)
        if match:
            return match.group(0)

        match = self.en_imperative_pattern.search(text)
        if match:
            return match.group(0)

        # Strategy 2: Check by lemma (for different verb forms)
        verb_found = self._find_verb_by_lemma(text)
        if verb_found:
            return verb_found

        return None

    def _find_verb_by_lemma(self, text: str) -> Optional[str]:
        """
        Find action verb by lemmatizing tokens.

        Args:
            text: Sentence text

        Returns:
            Found verb or None
        """
        # Skip if past tense passive context (not an action request)
        past_tense_indicators = [
            r"\b(был|была|было|были)\b",  # RU: был/была/было/были
            r"\b(was|were|has been|have been)\b",  # EN: was/were/has been/have been
            r"\b\w+(ли|ла|ло)\s+(вчера|утром|сегодня|уже)\b",  # RU: прислали утром, сделали вчера
            r"\b\w+ed\s+(yesterday|today|already)\b",  # EN: checked yesterday
        ]
        for pattern in past_tense_indicators:
            if re.search(pattern, text.lower()):
                # Skip: past tense passive, not action
                return None

        candidate_text = self._strip_leading_mention(text.lower())
        tokens = re.findall(r"\b\w+\b", candidate_text)
        if not tokens:
            return None

        polite_prefixes = {"please", "пожалуйста", "прошу"}
        while tokens and tokens[0] in polite_prefixes:
            tokens = tokens[1:]

        if not tokens:
            return None

        token = tokens[0]
        if not self._is_imperative_like(token):
            return None

        for token in tokens[:2]:
            # Lemmatize token
            lemma = self.lemmatizer.lemmatize_token(token, lang="auto")

            # Check if lemma is a known action verb
            if lemma in self.en_action_verbs or lemma in self.ru_action_verbs:
                logger.debug(
                    "Found action verb by lemma",
                    token=token,
                    lemma=lemma,
                    text_snippet=text[:50],
                )
                return lemma

        return None

    def _strip_leading_mention(self, text: str) -> str:
        """Remove leading direct mentions like 'Ivan,' before verb detection."""
        for alias in self.mention_aliases:
            if not alias or "@" in alias:
                continue

            pattern = re.compile(rf"^\s*{re.escape(alias)}[,:;\s-]+", re.IGNORECASE)
            if pattern.match(text):
                return pattern.sub("", text, count=1)

        return text

    def _is_imperative_like(self, token: str) -> bool:
        """Best-effort filter to avoid treating narrative verb forms as requests."""
        if not token:
            return False

        token_lower = token.lower()

        if re.fullmatch(r"[a-z]+", token_lower):
            if token_lower.endswith("ed") or token_lower.endswith("ing"):
                return False
            return True

        if re.search(r"[а-яё]", token_lower):
            if token_lower.endswith(("л", "ла", "ли", "ло")):
                return False
            return True

        return False

    def _find_action_marker(self, text: str) -> Optional[str]:
        """
        Find action marker in text.

        Strategy:
        1. Check regex patterns for explicit markers (нужно, need to, etc.)
        2. Check for action verbs by lemma
        """
        # Check Russian action markers
        match = self.ru_action_pattern.search(text)
        if match:
            return match.group(0)

        # Check English action markers
        match = self.en_action_pattern.search(text)
        if match:
            return match.group(0)

        return None

    def _is_question(self, text: str) -> bool:
        """Check if text is a question."""
        # Check Russian question markers
        if self.ru_question_pattern.search(text):
            return True

        # Check English question markers
        if self.en_question_pattern.search(text):
            return True

        return False

    def _extract_deadline(self, text: str) -> Optional[str]:
        """Extract deadline from text."""
        match = self.date_pattern.search(text)
        if match:
            return match.group(0)

        return None

    def _calculate_confidence(self, features: Dict[str, any]) -> float:
        """
        Calculate confidence score using logistic function.

        Features:
        - has_user_mention: bool
        - has_imperative: bool
        - has_action_marker: bool
        - is_question: bool
        - has_deadline: bool
        - sender_rank: float (0.0-1.0)

        Returns:
            Confidence score (0.0-1.0)
        """
        # Feature weights (tuned for precision/recall)
        weights = {
            "has_user_mention": 1.5,  # Strong signal
            "has_imperative": 1.2,  # Strong signal
            "has_action_marker": 1.0,  # Medium signal
            "is_question": 0.8,  # Medium signal
            "has_deadline": 0.6,  # Additional boost
            "sender_rank": 0.5,  # Weak signal
        }

        # Calculate weighted sum
        score = 0.0
        for feature, value in features.items():
            if feature in weights:
                weight = weights[feature]
                if isinstance(value, bool):
                    score += weight if value else 0
                else:
                    score += weight * float(value)

        # Logistic function: 1 / (1 + exp(-score + bias))
        bias = 1.5  # Shift threshold
        confidence = 1.0 / (1.0 + math.exp(-score + bias))

        # Clamp to [0.0, 1.0]
        confidence = max(0.0, min(1.0, confidence))

        return confidence


def enrich_actions_with_evidence(
    actions: List[ExtractedAction], evidence_chunks: List, msg_id: str
) -> List[ExtractedAction]:
    """
    Enrich actions with evidence_id.

    Args:
        actions: List of extracted actions
        evidence_chunks: All evidence chunks
        msg_id: Message ID to match

    Returns:
        Enriched actions with evidence_id set
    """
    # Find chunks from this message
    msg_chunks = [c for c in evidence_chunks if c.source_ref.get("msg_id") == msg_id]

    if not msg_chunks:
        logger.warning("No evidence chunks found for message", msg_id=msg_id)
        return actions

    # For each action, find best matching chunk
    for action in actions:
        best_chunk = None
        best_overlap = 0

        for chunk in msg_chunks:
            # Calculate overlap between action text and chunk content
            # Simple approach: check if action is substring of chunk
            if action.text in chunk.content:
                overlap = len(action.text)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_chunk = chunk
            # Or vice versa
            elif chunk.content in action.text:
                overlap = len(chunk.content)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_chunk = chunk

        if best_chunk:
            action.evidence_id = best_chunk.evidence_id
        else:
            # Fallback: use first chunk from message
            action.evidence_id = msg_chunks[0].evidence_id

    return actions
