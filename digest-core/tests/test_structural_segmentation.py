"""
Tests for structural segmentation in EvidenceSplitter.
"""

from datetime import datetime, timezone
from digest_core.evidence.split import EvidenceSplitter
from digest_core.ingest.ews import NormalizedMessage
from digest_core.threads.build import ConversationThread


def create_test_message(text_body: str, msg_id: str = "msg1") -> NormalizedMessage:
    """Create a test normalized message."""
    return NormalizedMessage(
        msg_id=msg_id,
        conversation_id="thread1",
        datetime_received=datetime.now(timezone.utc),
        sender_email="sender@example.com",
        subject="Test Subject",
        text_body=text_body,
        to_recipients=["user@example.com"],
        cc_recipients=[],
        importance="Normal",
        is_flagged=False,
        has_attachments=False,
        attachment_types=[],
    )


class TestStructuralSegmentation:
    """Test suite for structural break detection."""

    def test_markdown_headers_detected(self):
        """Test markdown headers create segment boundaries."""
        text = """
Introduction paragraph here.

# Main Header

Content under main header.

## Sub Header

More content here.

### Another Section

Final content.
"""
        splitter = EvidenceSplitter()
        breaks = splitter._detect_structural_breaks(text)

        # Should detect the 3 markdown headers
        assert len(breaks) >= 3

    def test_caps_headers_detected(self):
        """Test CAPS + colon headers detected."""
        text = """
Some introduction text.

IMPORTANT NOTICE:

Critical information here.

NEXT SECTION:

More content.

ЗАГОЛОВОК:

Russian header content.
"""
        splitter = EvidenceSplitter()
        breaks = splitter._detect_structural_breaks(text)

        # Should detect at least the CAPS headers
        assert len(breaks) >= 3

    def test_email_markers_detected(self):
        """Test 'On ... wrote:' creates boundaries."""
        text = """
My reply to the email.

On Mon, Dec 4, 2023 at 10:30 AM John Doe wrote:
Original email content here.

From: Alice Smith
More quoted content.

От: Иванов Иван
Russian quoted content.
"""
        splitter = EvidenceSplitter()
        breaks = splitter._detect_structural_breaks(text)

        # Should detect email markers
        assert len(breaks) >= 3

    def test_numbered_lists_detected(self):
        """Test numbered lists create boundaries."""
        text = """
Here are the action items:

1. First action item
2. Second action item
3. Third action item

And also:

1) Option A
2) Option B
"""
        splitter = EvidenceSplitter()
        breaks = splitter._detect_structural_breaks(text)

        # Should detect list markers (at least the numbered ones)
        assert len(breaks) >= 3

    def test_horizontal_rules_detected(self):
        """Test horizontal rules create boundaries."""
        text = """
Section one content.

---

Section two content.

***

Section three content.

========

Final section.
"""
        splitter = EvidenceSplitter()
        breaks = splitter._detect_structural_breaks(text)

        # Should detect horizontal rules
        assert len(breaks) >= 3

    def test_long_email_segmentation(self):
        """Test long email (>1000 tokens) splits intelligently."""
        # Create a long email with structure (>1000 tokens)
        long_text = (
            """
# Executive Summary

"""
            + " ".join(["Important content"] * 200)
            + """

# Technical Details

"""
            + " ".join(["Technical information"] * 200)
            + """

# Action Items

1. First task
2. Second task
3. Third task

---

# Appendix

"""
            + " ".join(["Additional details"] * 200)
        )

        message = create_test_message(long_text)
        thread = ConversationThread(
            conversation_id="thread1",
            messages=[message],
            latest_message_time=message.datetime_received,
            participant_count=2,
            message_count=1,
        )

        splitter = EvidenceSplitter()

        # Estimate tokens (should be >1000)
        estimated_tokens = len(long_text.split()) * 1.3
        assert estimated_tokens > 1000

        # Split with high load (should trigger adaptive chunking)
        chunks = splitter.split_evidence([thread], total_emails=250, total_threads=70)

        # Should create fewer chunks for long emails under high load
        assert len(chunks) <= 3  # max_chunks_if_long with adaptive multiplier

    def test_adaptive_chunking_high_load(self):
        """Test adaptive chunking reduces chunks under high load."""
        text = " ".join(["Content"] * 500)  # Medium length email
        message = create_test_message(text)
        thread = ConversationThread(
            conversation_id="thread1",
            messages=[message],
            latest_message_time=message.datetime_received,
            participant_count=1,
            message_count=1,
        )

        splitter = EvidenceSplitter()

        # Low load - should allow more chunks
        chunks_low = splitter.split_evidence([thread], total_emails=100, total_threads=30)

        # High load - should reduce chunks
        chunks_high = splitter.split_evidence([thread], total_emails=250, total_threads=70)

        # High load should produce fewer or equal chunks
        assert len(chunks_high) <= len(chunks_low)

    def test_adaptive_chunking_long_email(self):
        """Test long emails get fewer chunks."""
        # Short email
        short_text = " ".join(["Content"] * 200)
        message_short = create_test_message(short_text, "msg1")

        # Long email (>1000 tokens)
        long_text = " ".join(["Content"] * 1000)
        message_long = create_test_message(long_text, "msg2")

        thread_short = ConversationThread(
            conversation_id="thread1",
            messages=[message_short],
            latest_message_time=message_short.datetime_received,
            participant_count=1,
            message_count=1,
        )

        thread_long = ConversationThread(
            conversation_id="thread2",
            messages=[message_long],
            latest_message_time=message_long.datetime_received,
            participant_count=1,
            message_count=1,
        )

        splitter = EvidenceSplitter()

        chunks_short = splitter.split_evidence([thread_short], total_emails=100, total_threads=30)
        chunks_long = splitter.split_evidence([thread_long], total_emails=100, total_threads=30)

        # Long email should have fewer chunks (max 3)
        assert len(chunks_long) <= 3
        # Short email can have more
        assert len(chunks_short) >= len(chunks_long) or len(chunks_short) == 0
