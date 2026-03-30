"""
Simple integration test to verify the sender fix works end-to-end.
"""

from datetime import datetime, timezone
from digest_core.ingest.ews import NormalizedMessage
from digest_core.evidence.actions import ActionMentionExtractor


def test_sender_fix_integration():
    """Test that the sender fix prevents AttributeError in actions stage."""
    # Create extractor
    extractor = ActionMentionExtractor(user_aliases=["user@example.com"])

    # Create message with missing sender (the original problem case)
    msg = NormalizedMessage(
        msg_id="test-sender-fix",
        conversation_id="conv-sender-fix",
        datetime_received=datetime.now(timezone.utc),
        sender_email="",  # Empty sender_email
        subject="Test Subject",
        text_body="Please review this document by Friday.",
        to_recipients=["user@example.com"],
        cc_recipients=[],
        importance="Normal",
        is_flagged=False,
        has_attachments=False,
        attachment_types=[],
        # Canonical fields with empty sender
        from_email="",  # Empty from_email
        from_name=None,
        to_emails=["user@example.com"],
        cc_emails=[],
        message_id="test-sender-fix",
        body_norm="Please review this document by Friday.",
        received_at=datetime.now(timezone.utc),
    )

    # Test that msg.sender returns empty string (not AttributeError)
    assert msg.sender == ""

    # Test that actions extraction doesn't crash
    # This would previously fail with AttributeError: 'NormalizedMessage' has no attribute 'sender'
    actions = extractor.extract_mentions_actions(
        text=msg.text_body,
        msg_id=msg.msg_id,
        sender=msg.sender,  # This should be empty string, not crash
        sender_rank=0.5,
    )

    # Should return list (may be empty)
    assert isinstance(actions, list)

    # Test the fallback logic from run.py
    sender = msg.sender or msg.from_email or msg.sender_email or ""
    assert sender == ""

    # Test with valid sender
    msg_valid = NormalizedMessage(
        msg_id="test-sender-valid",
        conversation_id="conv-sender-valid",
        datetime_received=datetime.now(timezone.utc),
        sender_email="boss@company.com",
        subject="Urgent Task",
        text_body="Please complete the report by end of day.",
        to_recipients=["user@example.com"],
        cc_recipients=[],
        importance="High",
        is_flagged=True,
        has_attachments=False,
        attachment_types=[],
        # Canonical fields with valid sender
        from_email="boss@company.com",
        from_name="Boss Name",
        to_emails=["user@example.com"],
        cc_emails=[],
        message_id="test-sender-valid",
        body_norm="Please complete the report by end of day.",
        received_at=datetime.now(timezone.utc),
    )

    # Test that msg.sender returns valid email
    assert msg_valid.sender == "boss@company.com"

    # Test fallback logic
    sender_valid = msg_valid.sender or msg_valid.from_email or msg_valid.sender_email or ""
    assert sender_valid == "boss@company.com"

    # Test actions extraction with valid sender
    actions_valid = extractor.extract_mentions_actions(
        text=msg_valid.text_body,
        msg_id=msg_valid.msg_id,
        sender=msg_valid.sender,
        sender_rank=0.9,
    )

    assert isinstance(actions_valid, list)
