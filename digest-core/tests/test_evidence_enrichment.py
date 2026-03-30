"""
Tests for evidence enrichment with metadata and signals.
"""

import pytest
from datetime import datetime, timezone
from digest_core.evidence.signals import (
    extract_action_verbs,
    extract_dates,
    contains_question,
    normalize_datetime_to_tz,
    calculate_sender_rank,
)
from digest_core.evidence.split import EvidenceChunk, EvidenceSplitter
from digest_core.ingest.ews import NormalizedMessage
from digest_core.threads.build import ConversationThread
from digest_core.llm.gateway import LLMGateway
from digest_core.config import LLMConfig


class TestSignalsExtraction:
    """Tests for signal extraction utilities."""

    def test_extract_action_verbs_ru(self):
        """Test Russian action verbs extraction."""
        text = "Пожалуйста, проверьте документ. Нужно согласовать срочно!"
        verbs = extract_action_verbs(text)

        assert "пожалуйста" in verbs
        assert "проверьте" in verbs  # Check for actual word in text
        assert "нужно" in verbs
        assert "срочно" in verbs

    def test_extract_action_verbs_en(self):
        """Test English action verbs extraction."""
        text = "Please review the document. Need to approve ASAP by the deadline."
        verbs = extract_action_verbs(text)

        assert "please" in verbs
        assert "review" in verbs
        assert "need" in verbs
        assert "approve" in verbs
        assert "asap" in verbs
        assert "deadline" in verbs

    def test_extract_action_verbs_empty(self):
        """Test action verbs extraction from empty text."""
        assert extract_action_verbs("") == []
        assert extract_action_verbs(None) == []

    def test_extract_dates(self):
        """Test date extraction in various formats."""
        text = """
        Meeting on 25/12/2024.
        Deadline: 2024-12-31
        Please respond today or tomorrow.
        """
        dates = extract_dates(text)

        assert "25/12/2024" in dates
        assert "2024-12-31" in dates
        assert "today" in dates
        assert "tomorrow" in dates

    def test_extract_dates_ru(self):
        """Test Russian date extraction."""
        text = "Сегодня, завтра или послезавтра нужно завершить."
        dates = extract_dates(text)

        assert "сегодня" in dates
        assert "завтра" in dates
        assert "послезавтра" in dates

    def test_contains_question_true(self):
        """Test question detection."""
        assert contains_question("Can you help?") is True
        assert contains_question("Можете ли вы помочь?") is True

    def test_contains_question_false(self):
        """Test question detection with no question."""
        assert contains_question("This is a statement.") is False
        assert contains_question("") is False

    def test_normalize_datetime_to_tz(self):
        """Test datetime normalization to timezone."""
        dt = datetime(2024, 12, 25, 12, 0, 0, tzinfo=timezone.utc)

        # Convert to Moscow timezone
        result = normalize_datetime_to_tz(dt, "Europe/Moscow")
        assert "2024-12-25" in result
        assert "+03:00" in result  # Moscow is UTC+3

    def test_calculate_sender_rank(self):
        """Test sender rank calculation (placeholder)."""
        rank = calculate_sender_rank("user@example.com")
        assert rank == 1  # Current implementation always returns 1


class TestEvidenceChunkCreation:
    """Tests for EvidenceChunk creation with metadata."""

    def create_test_message(self, **kwargs):
        """Helper to create a test NormalizedMessage."""
        defaults = {
            "msg_id": "test-msg-1",
            "conversation_id": "conv-1",
            "datetime_received": datetime(2024, 12, 25, 12, 0, 0, tzinfo=timezone.utc),
            "sender_email": "sender@example.com",
            "subject": "Test Subject",
            "text_body": """Test body content with enough text to meet minimum token requirements.
                This is a longer message to ensure it gets processed. We need at least 64 tokens
                to meet the minimum chunk size. Adding more content here to reach that threshold.
                Please review this document and provide feedback. Thank you for your attention
                to this matter. We appreciate your prompt response.""",
            "to_recipients": ["user@example.com"],
            "cc_recipients": [],
            "importance": "Normal",
            "is_flagged": False,
            "has_attachments": False,
            "attachment_types": [],
        }
        defaults.update(kwargs)
        return NormalizedMessage(**defaults)

    def test_evidence_chunk_with_metadata(self):
        """Test EvidenceChunk creation with full metadata."""
        message = self.create_test_message(
            importance="High",
            is_flagged=True,
            has_attachments=True,
            attachment_types=["pdf", "xlsx"],
        )

        thread = ConversationThread(
            conversation_id="conv-1",
            messages=[message],
            latest_message_time=message.datetime_received,
            participant_count=2,
            message_count=1,
        )

        splitter = EvidenceSplitter(
            user_aliases=["user@example.com"], user_timezone="Europe/Moscow"
        )

        chunks = splitter.split_evidence([thread])

        assert len(chunks) > 0
        chunk = chunks[0]

        # Check metadata
        assert chunk.message_metadata["from"] == "sender@example.com"
        assert "user@example.com" in chunk.message_metadata["to"]
        assert chunk.message_metadata["importance"] == "High"
        assert chunk.message_metadata["is_flagged"] is True
        assert chunk.message_metadata["has_attachments"] is True
        assert "pdf" in chunk.message_metadata["attachment_types"]
        assert "xlsx" in chunk.message_metadata["attachment_types"]

    def test_addressed_to_me_detection(self):
        """Test AddressedToMe detection with aliases."""
        message = self.create_test_message(
            to_recipients=["alias1@example.com", "other@example.com"],
            cc_recipients=["alias2@example.com"],
        )

        thread = ConversationThread(
            conversation_id="conv-1",
            messages=[message],
            latest_message_time=message.datetime_received,
            participant_count=3,
            message_count=1,
        )

        splitter = EvidenceSplitter(
            user_aliases=["alias1@example.com", "alias2@example.com"],
            user_timezone="Europe/Moscow",
        )

        chunks = splitter.split_evidence([thread])

        assert len(chunks) > 0
        chunk = chunks[0]

        assert chunk.addressed_to_me is True
        assert "alias1@example.com" in chunk.user_aliases_matched
        assert "alias2@example.com" in chunk.user_aliases_matched

    def test_addressed_to_me_false(self):
        """Test AddressedToMe when user is not in recipients."""
        message = self.create_test_message(to_recipients=["other@example.com"], cc_recipients=[])

        thread = ConversationThread(
            conversation_id="conv-1",
            messages=[message],
            latest_message_time=message.datetime_received,
            participant_count=2,
            message_count=1,
        )

        splitter = EvidenceSplitter(
            user_aliases=["user@example.com"], user_timezone="Europe/Moscow"
        )

        chunks = splitter.split_evidence([thread])

        assert len(chunks) > 0
        chunk = chunks[0]

        assert chunk.addressed_to_me is False
        assert len(chunk.user_aliases_matched) == 0

    def test_signals_extraction_in_chunk(self):
        """Test signal extraction during chunk creation."""
        message = self.create_test_message(
            text_body="""Please review this document by 2024-12-31. Can you approve?
                This is important and needs your attention. The deadline is approaching soon.
                Please provide your feedback as soon as possible. We need at least 64 tokens
                to meet the minimum chunk size. Adding more content here to reach that threshold.
                Thank you for your cooperation and prompt response to this request.""",
            has_attachments=True,
            attachment_types=["pdf"],
        )

        thread = ConversationThread(
            conversation_id="conv-1",
            messages=[message],
            latest_message_time=message.datetime_received,
            participant_count=2,
            message_count=1,
        )

        splitter = EvidenceSplitter(
            user_aliases=["user@example.com"], user_timezone="Europe/Moscow"
        )

        chunks = splitter.split_evidence([thread])

        assert len(chunks) > 0
        chunk = chunks[0]

        # Check signals
        assert "please" in chunk.signals["action_verbs"]
        assert "review" in chunk.signals["action_verbs"]
        assert "approve" in chunk.signals["action_verbs"]
        assert "2024-12-31" in chunk.signals["dates"]
        assert chunk.signals["contains_question"] is True
        assert chunk.signals["sender_rank"] == 1
        assert "pdf" in chunk.signals["attachments"]


class TestPrepareEvidenceText:
    """Tests for prepare_evidence_text with metadata."""

    def create_test_chunk(self, **kwargs):
        """Helper to create a test EvidenceChunk."""
        defaults = {
            "evidence_id": "ev-123",
            "conversation_id": "conv-1",
            "content": "Test content",
            "source_ref": {
                "type": "email",
                "msg_id": "msg-1",
                "conversation_id": "conv-1",
                "message_index": 0,
                "chunk_index": 0,
            },
            "token_count": 10,
            "priority_score": 5.0,
            "message_metadata": {
                "from": "sender@example.com",
                "to": ["user@example.com"],
                "cc": [],
                "subject": "Test Subject",
                "received_at": "2024-12-25T12:00:00+03:00",
                "importance": "Normal",
                "is_flagged": False,
                "has_attachments": False,
                "attachment_types": [],
            },
            "addressed_to_me": True,
            "user_aliases_matched": ["user@example.com"],
            "signals": {
                "action_verbs": ["please", "review"],
                "dates": ["2024-12-31"],
                "contains_question": True,
                "sender_rank": 1,
                "attachments": [],
            },
        }
        defaults.update(kwargs)
        return EvidenceChunk(**defaults)

    def test_prepare_evidence_text_with_metadata(self):
        """Test evidence text preparation with full metadata."""
        chunk = self.create_test_chunk()

        # Create a mock LLMGateway to test _prepare_evidence_text
        config = LLMConfig(endpoint="http://test", model="test-model")
        gateway = LLMGateway(config)

        result = gateway._prepare_evidence_text([chunk])

        # Check that all metadata is present
        assert "Evidence 1" in result
        assert "ev-123" in result
        assert "msg-1" in result
        assert "conv-1" in result
        assert "sender@example.com" in result
        assert "user@example.com" in result
        assert "Test Subject" in result
        assert "2024-12-25T12:00:00+03:00" in result
        assert "Normal" in result
        assert "False" in result  # is_flagged
        assert "AddressedToMe: True" in result
        assert "please, review" in result
        assert "2024-12-31" in result
        assert "contains_question=True" in result
        assert "Test content" in result

    def test_prepare_evidence_text_missing_fields(self):
        """Test evidence text preparation with missing fields (robustness)."""
        # Create a minimal chunk (old format without new fields)
        minimal_chunk = EvidenceChunk(
            evidence_id="ev-456",
            conversation_id="conv-2",
            content="Minimal content",
            source_ref={
                "type": "email",
                "msg_id": "msg-2",
                "conversation_id": "conv-2",
            },
            token_count=5,
            priority_score=1.0,
            message_metadata={},  # Empty metadata
            addressed_to_me=False,
            user_aliases_matched=[],
            signals={},  # Empty signals
        )

        config = LLMConfig(endpoint="http://test", model="test-model")
        gateway = LLMGateway(config)

        # Should not raise an exception
        result = gateway._prepare_evidence_text([minimal_chunk])

        assert "Evidence 1" in result
        assert "ev-456" in result
        assert "N/A" in result  # For missing fields
        assert "Minimal content" in result

    def test_prepare_evidence_text_long_recipients(self):
        """Test evidence text with many recipients (truncation)."""
        chunk = self.create_test_chunk(
            message_metadata={
                "from": "sender@example.com",
                "to": [f"user{i}@example.com" for i in range(10)],
                "cc": [f"cc{i}@example.com" for i in range(5)],
                "subject": "Test Subject",
                "received_at": "2024-12-25T12:00:00+03:00",
                "importance": "Normal",
                "is_flagged": False,
                "has_attachments": False,
                "attachment_types": [],
            }
        )

        config = LLMConfig(endpoint="http://test", model="test-model")
        gateway = LLMGateway(config)

        result = gateway._prepare_evidence_text([chunk])

        # Check that recipients are truncated
        assert "(+7 more)" in result  # 10 recipients, showing 3 + "7 more"
        assert "(+2 more)" in result  # 5 cc, showing 3 + "2 more"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
