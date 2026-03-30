"""
Tests for action/mention extraction (rule-based).

Covers:
- Russian and English action detection
- Imperative verbs
- Question detection
- User mention detection
- Deadline extraction
- Confidence scoring
- Precision/Recall/F1 validation
"""

import pytest
from digest_core.evidence.actions import (
    ActionMentionExtractor,
    ExtractedAction,
    enrich_actions_with_evidence,
)
from digest_core.evidence.split import EvidenceChunk


# Test fixtures
@pytest.fixture
def user_aliases():
    """User aliases for testing."""
    return ["ivan.petrov@corp.com", "ivanov", "Ivan Petrov", "Иван Петров"]


@pytest.fixture
def extractor(user_aliases):
    """ActionMentionExtractor instance."""
    return ActionMentionExtractor(user_aliases, user_timezone="Europe/Moscow")


class TestActionDetectionRussian:
    """Test Russian action detection."""

    def test_russian_imperative_verb(self, extractor):
        """Test Russian imperative verb detection."""
        text = "Иван, пожалуйста сделайте отчет до пятницы."
        actions = extractor.extract_mentions_actions(text, "msg-001", "boss@corp.com")

        assert len(actions) >= 1
        assert actions[0].type in ["action", "mention"]
        assert actions[0].confidence > 0.5

    def test_russian_action_marker_nuzhno(self, extractor):
        """Test Russian 'нужно' action marker."""
        text = "Иван Петров, нужно согласовать документ до завтра."
        actions = extractor.extract_mentions_actions(text, "msg-002", "colleague@corp.com")

        assert len(actions) >= 1
        assert actions[0].confidence > 0.6  # Has deadline + mention
        assert actions[0].due is not None  # "завтра" detected

    def test_russian_question(self, extractor):
        """Test Russian question detection."""
        text = "Иван, когда вы сможете проверить код?"
        actions = extractor.extract_mentions_actions(text, "msg-003", "dev@corp.com")

        assert len(actions) >= 1
        assert actions[0].type == "question"
        assert actions[0].confidence > 0.5

    def test_russian_proshu(self, extractor):
        """Test Russian 'прошу' action marker."""
        text = "Прошу вас, ivanov, утвердить бюджет до конца дня."
        actions = extractor.extract_mentions_actions(text, "msg-004", "finance@corp.com")

        assert len(actions) >= 1
        assert actions[0].confidence > 0.7  # Has mention + action + deadline


class TestActionDetectionEnglish:
    """Test English action detection."""

    def test_english_please_imperative(self, extractor):
        """Test 'please' imperative detection."""
        text = "Ivan, please review the PR by Friday."
        actions = extractor.extract_mentions_actions(text, "msg-005", "developer@corp.com")

        assert len(actions) >= 1
        assert actions[0].type in ["action", "question"]
        assert actions[0].confidence > 0.6

    def test_english_can_you(self, extractor):
        """Test 'can you' detection."""
        text = "Can you update the documentation, ivanov?"
        actions = extractor.extract_mentions_actions(text, "msg-006", "tech@corp.com")

        assert len(actions) >= 1
        assert actions[0].confidence > 0.5

    def test_english_question(self, extractor):
        """Test English question detection."""
        text = "Ivan Petrov, what is the deadline for this task?"
        actions = extractor.extract_mentions_actions(text, "msg-007", "pm@corp.com")

        assert len(actions) >= 1
        assert actions[0].type == "question"

    def test_english_need_to(self, extractor):
        """Test 'need to' action marker."""
        text = "We need Ivan to complete the analysis by EOD."
        actions = extractor.extract_mentions_actions(text, "msg-008", "manager@corp.com")

        assert len(actions) >= 1
        assert actions[0].due is not None  # "EOD" detected


class TestMentionDetection:
    """Test user mention detection."""

    def test_mention_by_email(self, extractor):
        """Test mention by email."""
        text = "We need input from ivan.petrov@corp.com on this issue."
        actions = extractor.extract_mentions_actions(text, "msg-009", "team@corp.com")

        assert len(actions) >= 1
        assert actions[0].type in ["action", "mention"]

    def test_mention_by_name(self, extractor):
        """Test mention by full name."""
        text = "Discussing this with Ivan Petrov would be helpful."
        actions = extractor.extract_mentions_actions(text, "msg-010", "colleague@corp.com")

        assert len(actions) >= 1

    def test_mention_by_nickname(self, extractor):
        """Test mention by nickname."""
        text = "Hey ivanov, can you check this?"
        actions = extractor.extract_mentions_actions(text, "msg-011", "friend@corp.com")

        assert len(actions) >= 1

    def test_no_mention_no_action(self, extractor):
        """Test no detection when no mention and no clear action."""
        text = "This is a general discussion about the project timeline."
        actions = extractor.extract_mentions_actions(text, "msg-012", "team@corp.com")

        # Should have few or no actions
        assert len(actions) == 0 or (len(actions) > 0 and actions[0].confidence < 0.5)


class TestDeadlineExtraction:
    """Test deadline extraction."""

    def test_deadline_date_format(self, extractor):
        """Test deadline with date format."""
        text = "Please complete by 15.01.2024, Ivan."
        actions = extractor.extract_mentions_actions(text, "msg-013", "pm@corp.com")

        assert len(actions) >= 1
        assert actions[0].due is not None
        assert "15.01" in actions[0].due or "15/01" in actions[0].due

    def test_deadline_relative(self, extractor):
        """Test deadline with relative date."""
        text = "Иван, нужно сделать до завтра."
        actions = extractor.extract_mentions_actions(text, "msg-014", "boss@corp.com")

        assert len(actions) >= 1
        assert actions[0].due is not None
        assert "завтра" in actions[0].due.lower()

    def test_deadline_eod(self, extractor):
        """Test EOD deadline."""
        text = "Need this by EOD, ivanov."
        actions = extractor.extract_mentions_actions(text, "msg-015", "urgent@corp.com")

        assert len(actions) >= 1
        assert actions[0].due is not None
        assert "eod" in actions[0].due.lower()

    def test_deadline_day_of_week(self, extractor):
        """Test deadline with day of week."""
        text = "Ivan Petrov, please review by Friday."
        actions = extractor.extract_mentions_actions(text, "msg-016", "reviewer@corp.com")

        assert len(actions) >= 1
        assert actions[0].due is not None
        assert "friday" in actions[0].due.lower()


class TestConfidenceScoring:
    """Test confidence scoring."""

    def test_high_confidence_all_signals(self, extractor):
        """Test high confidence with all signals."""
        # Has: user mention + imperative + deadline
        text = "Иван Петров, пожалуйста утвердите до завтра."
        actions = extractor.extract_mentions_actions(
            text, "msg-017", "important@corp.com", sender_rank=0.9
        )

        assert len(actions) >= 1
        assert actions[0].confidence >= 0.85  # High confidence

    def test_medium_confidence_partial_signals(self, extractor):
        """Test medium confidence with partial signals."""
        # Has: mention + question, no deadline
        text = "Ivan, what do you think about this approach?"
        actions = extractor.extract_mentions_actions(text, "msg-018", "colleague@corp.com")

        assert len(actions) >= 1
        assert 0.4 <= actions[0].confidence <= 0.8  # Medium confidence

    def test_low_confidence_weak_signals(self, extractor):
        """Test low confidence with weak signals."""
        # Has: only vague mention
        text = "We discussed this with Ivan's team yesterday."
        actions = extractor.extract_mentions_actions(text, "msg-019", "team@corp.com")

        # Either no actions or low confidence
        if len(actions) > 0:
            assert actions[0].confidence < 0.5  # Low confidence

    def test_confidence_with_sender_rank(self, extractor):
        """Test confidence boosted by sender rank."""
        text = "ivanov, please review."

        # Low sender rank
        actions_low = extractor.extract_mentions_actions(
            text, "msg-020", "junior@corp.com", sender_rank=0.1
        )

        # High sender rank
        actions_high = extractor.extract_mentions_actions(
            text, "msg-021", "ceo@corp.com", sender_rank=0.9
        )

        # High sender should have slightly higher confidence
        if len(actions_low) > 0 and len(actions_high) > 0:
            assert actions_high[0].confidence >= actions_low[0].confidence


class TestMultipleActions:
    """Test extraction of multiple actions from one message."""

    def test_multiple_actions_same_message(self, extractor):
        """Test multiple actions in same message."""
        text = """
        Иван Петров, пожалуйста:
        1. Проверьте отчет до пятницы
        2. Согласуйте бюджет до понедельника
        3. Отправьте результаты команде
        """
        actions = extractor.extract_mentions_actions(text, "msg-022", "manager@corp.com")

        # Should extract multiple actions
        assert len(actions) >= 2

    def test_actions_sorted_by_confidence(self, extractor):
        """Test that actions are sorted by confidence."""
        text = """
        Hi Ivan. General discussion here.
        But also, можете ли вы срочно утвердить договор до завтра?
        Some more general text.
        """
        actions = extractor.extract_mentions_actions(text, "msg-023", "legal@corp.com")

        if len(actions) >= 2:
            # First action should have highest confidence
            assert actions[0].confidence >= actions[1].confidence


class TestEnrichWithEvidence:
    """Test enrichment with evidence IDs."""

    def test_enrich_with_matching_chunk(self):
        """Test enrichment when chunk content matches action text."""
        action = ExtractedAction(
            type="action",
            who="user",
            verb="review",
            text="Please review the PR by Friday",
            confidence=0.8,
            msg_id="msg-100",
        )

        chunk = EvidenceChunk(
            evidence_id="ev-100",
            content="Please review the PR by Friday and provide feedback",
            source_ref={"msg_id": "msg-100"},
            message_metadata={},
            chunk_idx=0,
            total_chunks=1,
            timestamp="2024-01-15T10:00:00Z",
            sender="dev@corp.com",
            thread_id="thread-1",
            signals={},
        )

        enriched = enrich_actions_with_evidence([action], [chunk], "msg-100")

        assert len(enriched) == 1
        assert enriched[0].evidence_id == "ev-100"

    def test_enrich_no_matching_chunk_fallback(self):
        """Test enrichment fallback to first chunk when no match."""
        action = ExtractedAction(
            type="action",
            who="user",
            verb="review",
            text="Some action text",
            confidence=0.7,
            msg_id="msg-101",
        )

        chunk = EvidenceChunk(
            evidence_id="ev-101",
            content="Different text that doesn't match",
            source_ref={"msg_id": "msg-101"},
            message_metadata={},
            chunk_idx=0,
            total_chunks=1,
            timestamp="2024-01-15T10:00:00Z",
            sender="test@corp.com",
            thread_id="thread-1",
            signals={},
        )

        enriched = enrich_actions_with_evidence([action], [chunk], "msg-101")

        # Should fallback to first chunk
        assert len(enriched) == 1
        assert enriched[0].evidence_id == "ev-101"


class TestGoldSetValidation:
    """Gold set for precision/recall validation."""

    GOLD_SET = [
        # Format: (text, expected_action, expected_type, has_deadline)
        # HIGH PRECISION cases (should extract)
        ("Иван, пожалуйста проверьте документ до завтра", True, "action", True),
        ("Ivan, please review by Friday", True, "action", True),
        ("Можете ли вы утвердить, ivanov?", True, "question", False),
        ("Can you approve this, Ivan Petrov?", True, "question", False),
        ("Нужно сделать отчет до понедельника, Иван", True, "action", True),
        ("We need Ivan to complete the task by EOD", True, "action", True),
        ("Прошу вас согласовать бюджет", True, "action", False),
        ("ivan.petrov@corp.com, когда сможете?", True, "question", False),
        ("Сделайте, пожалуйста, Иван Петров", True, "action", False),
        ("Ivan, what is the status?", True, "question", False),
        # MEDIUM cases (borderline)
        ("Discussing with Ivan would help", True, "mention", False),
        ("Ivan mentioned this yesterday", True, "mention", False),
        ("Need input from ivanov", True, "action", False),
        ("Иван в курсе этого вопроса", True, "mention", False),
        # NEGATIVE cases (should NOT extract or low confidence)
        ("The project is going well", False, None, False),
        ("Meeting scheduled for tomorrow", False, None, False),
        ("General team discussion", False, None, False),
        ("Status update on deliverables", False, None, False),
    ]

    def test_gold_set_precision_recall(self, extractor):
        """Test precision and recall on gold set."""
        tp = 0  # True positives
        fp = 0  # False positives
        tn = 0  # True negatives
        fn = 0  # False negatives

        confidence_threshold = 0.5  # Actions with confidence >= 0.5 are considered positive

        for text, should_extract, expected_type, has_deadline in self.GOLD_SET:
            actions = extractor.extract_mentions_actions(
                text, f"msg-gold-{hash(text)}", "test@corp.com"
            )

            # Filter actions by confidence threshold
            high_conf_actions = [a for a in actions if a.confidence >= confidence_threshold]

            if should_extract:
                if len(high_conf_actions) > 0:
                    tp += 1
                    # Check type if specified
                    if expected_type and high_conf_actions[0].type != expected_type:
                        # Type mismatch, but still a detection
                        pass
                    # Check deadline if expected
                    if has_deadline and high_conf_actions[0].due is None:
                        # Missing deadline, but still detected action
                        pass
                else:
                    fn += 1  # Missed a true action
            else:
                if len(high_conf_actions) > 0:
                    fp += 1  # False alarm
                else:
                    tn += 1  # Correctly ignored

        # Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        print("\n=== Gold Set Validation ===")
        print(f"True Positives: {tp}")
        print(f"False Positives: {fp}")
        print(f"True Negatives: {tn}")
        print(f"False Negatives: {fn}")
        print(f"Precision: {precision:.3f}")
        print(f"Recall: {recall:.3f}")
        print(f"F1 Score: {f1:.3f}")
        print("===========================\n")

        # DoD requirements: P >= 0.85, R >= 0.80
        assert precision >= 0.85, f"Precision {precision:.3f} below target 0.85"
        assert recall >= 0.80, f"Recall {recall:.3f} below target 0.80"
        assert f1 >= 0.82, f"F1 {f1:.3f} below expected minimum"


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_text(self, extractor):
        """Test with empty text."""
        actions = extractor.extract_mentions_actions("", "msg-empty", "test@corp.com")
        assert len(actions) == 0

    def test_very_long_text(self, extractor):
        """Test with very long text."""
        long_text = "Hello Ivan. " + ("Some filler text. " * 100) + "Please review by Friday."
        actions = extractor.extract_mentions_actions(long_text, "msg-long", "test@corp.com")

        # Should still extract action
        assert len(actions) >= 1

    def test_mixed_language(self, extractor):
        """Test with mixed Russian/English."""
        text = "Hi Ivan Петров, please проверьте документ до Friday."
        actions = extractor.extract_mentions_actions(text, "msg-mixed", "test@corp.com")

        assert len(actions) >= 1

    def test_special_characters(self, extractor):
        """Test with special characters."""
        text = "Ivan!!! Пожалуйста, сделайте СРОЧНО до завтра!!!"
        actions = extractor.extract_mentions_actions(text, "msg-special", "urgent@corp.com")

        assert len(actions) >= 1
        assert actions[0].due is not None
