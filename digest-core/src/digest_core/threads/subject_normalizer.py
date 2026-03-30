"""
Subject normalization for robust threading.

Removes:
- RE/FW/Ответ/Пересл prefixes (RU/EN)
- (External) markers
- [Tags] in brackets
- Emoji
- Extra whitespace/quotes/dashes

Preserves original for display.
"""

import re
import unicodedata
import structlog
from typing import Tuple

logger = structlog.get_logger()


class SubjectNormalizer:
    """Normalize email subjects for threading."""

    # Russian reply/forward prefixes
    RU_PREFIXES = [
        r"^Ответ:\s*",
        r"^Отв:\s*",
        r"^RE:\s*",
        r"^Пересл:\s*",
        r"^Fwd:\s*",
        r"^ПЕР:\s*",
    ]

    # English reply/forward prefixes
    EN_PREFIXES = [
        r"^Re:\s*",
        r"^RE:\s*",
        r"^Fw:\s*",
        r"^FW:\s*",
        r"^Fwd:\s*",
        r"^FWD:\s*",
    ]

    # External markers
    EXTERNAL_MARKERS = [
        r"\(External\)",
        r"\[External\]",
        r"\(EXTERNAL\)",
        r"\[EXTERNAL\]",
        r"\(внешний\)",
        r"\[внешний\]",
    ]

    # Tag patterns in brackets/parentheses
    TAG_PATTERNS = [
        r"\[[^\]]{1,50}\]",  # [JIRA-123], [URGENT], etc.
        r"\([^)]{1,50}\)",  # (tag), (project), etc.
    ]

    def __init__(self):
        """Initialize SubjectNormalizer."""
        # Compile regex patterns for performance
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile all regex patterns."""
        # Combine all prefixes
        all_prefixes = self.RU_PREFIXES + self.EN_PREFIXES
        self.prefix_pattern = re.compile("|".join(all_prefixes), re.IGNORECASE)

        # External markers
        self.external_pattern = re.compile("|".join(self.EXTERNAL_MARKERS), re.IGNORECASE)

        # Tags
        self.tag_pattern = re.compile("|".join(self.TAG_PATTERNS))

        # Emoji pattern (Unicode ranges for emoji)
        # https://unicode.org/emoji/charts/full-emoji-list.html
        self.emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags (iOS)
            "\U00002700-\U000027bf"  # Dingbats
            "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
            "\U00002600-\U000026ff"  # Miscellaneous Symbols
            "\U0001f190-\U0001f1ff"  # Regional Indicator Symbols
            "]+",
            flags=re.UNICODE,
        )

    def normalize(self, subject: str) -> Tuple[str, str]:
        """
        Normalize subject for threading.

        Args:
            subject: Original subject string

        Returns:
            Tuple of (normalized_subject, original_subject)
        """
        if not subject:
            return "", ""

        original = subject.strip()
        normalized = original

        # Step 1: Remove prefixes (iteratively, as they may be nested)
        # RE: RE: FW: Subject → Subject
        max_iterations = 10  # Prevent infinite loop
        for _ in range(max_iterations):
            before = normalized
            normalized = self.prefix_pattern.sub("", normalized).strip()
            if normalized == before:
                break  # No more prefixes found

        # Step 2: Remove external markers
        normalized = self.external_pattern.sub("", normalized).strip()

        # Step 3: Remove tags in brackets
        normalized = self.tag_pattern.sub("", normalized).strip()

        # Step 4: Remove emoji
        normalized = self.emoji_pattern.sub("", normalized).strip()

        # Step 5: Normalize quotes (smart quotes → straight quotes)
        normalized = self._normalize_quotes(normalized)

        # Step 6: Normalize dashes (em/en dash → hyphen)
        normalized = self._normalize_dashes(normalized)

        # Step 7: Normalize whitespace (multiple spaces → single space)
        normalized = " ".join(normalized.split())

        # Step 8: Convert to lowercase for comparison
        normalized = normalized.lower()

        # Step 9: Unicode normalization (NFC)
        normalized = unicodedata.normalize("NFC", normalized)

        logger.debug(
            "Subject normalized",
            original_len=len(original),
            normalized_len=len(normalized),
            original_preview=original[:50],
            normalized_preview=normalized[:50],
        )

        return normalized, original

    def _normalize_quotes(self, text: str) -> str:
        """Normalize smart quotes to straight quotes."""
        # Smart single quotes
        text = text.replace("'", "'").replace("'", "'")
        # Smart double quotes
        text = text.replace(""", '"').replace(""", '"')
        text = text.replace("«", '"').replace("»", '"')
        return text

    def _normalize_dashes(self, text: str) -> str:
        """Normalize em/en dashes to hyphen."""
        # Em dash (—)
        text = text.replace("—", "-")
        # En dash (–)
        text = text.replace("–", "-")
        return text

    def is_similar(self, subject1: str, subject2: str) -> bool:
        """
        Check if two subjects are similar after normalization.

        Args:
            subject1: First subject
            subject2: Second subject

        Returns:
            True if normalized subjects match
        """
        norm1, _ = self.normalize(subject1)
        norm2, _ = self.normalize(subject2)

        # Empty subjects are not similar
        if not norm1 or not norm2:
            return False

        return norm1 == norm2


def calculate_text_similarity(text1: str, text2: str, max_chars: int = 200) -> float:
    """
    Calculate cosine similarity between first N characters of two texts.

    Uses character n-grams for simplicity (no external dependencies).

    Args:
        text1: First text
        text2: Second text
        max_chars: Max characters to compare

    Returns:
        Similarity score (0.0-1.0)
    """
    if not text1 or not text2:
        return 0.0

    # Truncate and normalize
    text1 = text1[:max_chars].lower()
    text2 = text2[:max_chars].lower()

    # Create character n-grams (n=3 for trigrams)
    def get_ngrams(text, n=3):
        """Get character n-grams."""
        ngrams = set()
        for i in range(len(text) - n + 1):
            ngrams.add(text[i : i + n])
        return ngrams

    ngrams1 = get_ngrams(text1)
    ngrams2 = get_ngrams(text2)

    if not ngrams1 or not ngrams2:
        return 0.0

    # Jaccard similarity (simpler than cosine, but effective)
    intersection = len(ngrams1 & ngrams2)
    union = len(ngrams1 | ngrams2)

    similarity = intersection / union if union > 0 else 0.0

    return similarity
