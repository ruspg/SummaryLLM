"""
Test minimum bucket guarantees for context selector.

Ensures that:
- At least 1 chunk from dates_deadlines is always included (if available)
- At least 1 chunk from addressed_to_me is always included (if available)
- Deduplication is by (msg_id, start, end) only, not semantic
"""

from digest_core.select.context import ContextSelector
from digest_core.evidence.split import EvidenceChunk


def make_chunk(
    evidence_id,
    msg_id,
    start=0,
    end=100,
    priority_score=1.0,
    addressed_to_me=False,
    dates=None,
    token_count=50,
    conversation_id="conv-1",
):
    """Helper to create evidence chunk for testing."""
    return EvidenceChunk(
        evidence_id=evidence_id,
        conversation_id=conversation_id,
        content=f"Test content for {evidence_id}",
        token_count=token_count,
        priority_score=priority_score,
        source_ref={"msg_id": msg_id, "start": start, "end": end, "type": "email"},
        message_metadata={
            "from": "test@example.com",
            "to": ["user@example.com"],
            "subject": f"Test {evidence_id}",
            "received_at": "2024-01-15T10:00:00Z",
            "importance": "Normal",
            "is_flagged": False,
            "has_attachments": False,
            "attachment_types": [],
        },
        addressed_to_me=addressed_to_me,
        user_aliases_matched=[],
        signals={
            "action_verbs": [],
            "dates": dates or [],
            "contains_question": False,
            "sender_rank": 1,
        },
    )


def test_deadline_always_included():
    """Test that a single deadline chunk is always included, even with low score."""
    selector = ContextSelector()

    # Create chunks: 1 with deadline (low score), many without (high scores)
    chunks = [
        # High priority chunks without deadline
        make_chunk("ev-1", "msg-1", priority_score=10.0, token_count=100),
        make_chunk("ev-2", "msg-2", priority_score=9.0, token_count=100),
        make_chunk("ev-3", "msg-3", priority_score=8.0, token_count=100),
        # LOW priority chunk WITH deadline - should still be included
        make_chunk(
            "ev-deadline",
            "msg-deadline",
            priority_score=0.1,
            dates=["2024-12-31"],
            token_count=100,
        ),
    ]

    # Select context
    selected = selector.select_context(chunks)

    # Verify deadline chunk is included despite low score
    selected_ids = [c.evidence_id for c in selected]
    assert "ev-deadline" in selected_ids, "Deadline chunk must be included even with low score"

    # Verify at least 1 from dates_deadlines bucket
    metrics = selector.get_metrics()
    assert (
        metrics["selected_by_bucket"]["dates_deadlines"] >= 1
    ), "At least 1 chunk from dates_deadlines must be selected"


def test_addressed_to_me_always_included():
    """Test that at least 1 addressed_to_me chunk is included (if available)."""
    selector = ContextSelector()

    # Create chunks: 1 addressed to me (low score), many not (high scores)
    chunks = [
        # High priority chunks not addressed to me
        make_chunk("ev-1", "msg-1", priority_score=10.0, token_count=100),
        make_chunk("ev-2", "msg-2", priority_score=9.0, token_count=100),
        make_chunk("ev-3", "msg-3", priority_score=8.0, token_count=100),
        # LOW priority chunk addressed to me - should still be included
        make_chunk(
            "ev-tome",
            "msg-tome",
            priority_score=0.1,
            addressed_to_me=True,
            token_count=100,
        ),
    ]

    # Select context
    selected = selector.select_context(chunks)

    # Verify addressed_to_me chunk is included despite low score
    selected_ids = [c.evidence_id for c in selected]
    assert "ev-tome" in selected_ids, "addressed_to_me chunk must be included even with low score"

    # Verify at least 1 from addressed_to_me bucket
    metrics = selector.get_metrics()
    assert (
        metrics["selected_by_bucket"]["addressed_to_me"] >= 1
    ), "At least 1 chunk from addressed_to_me must be selected"


def test_deduplication_by_msg_id_start_end():
    """Test that deduplication is only by (msg_id, start, end), not semantic."""
    selector = ContextSelector()

    # Create duplicate chunks (same msg_id, start, end)
    chunks = [
        make_chunk("ev-1", "msg-1", start=0, end=100, priority_score=10.0),
        make_chunk("ev-2", "msg-1", start=0, end=100, priority_score=9.0),  # DUPLICATE
        # Different start/end - should NOT be deduplicated
        make_chunk("ev-3", "msg-1", start=100, end=200, priority_score=8.0),
        # Different msg_id - should NOT be deduplicated
        make_chunk("ev-4", "msg-2", start=0, end=100, priority_score=7.0),
    ]

    # Select context
    selected = selector.select_context(chunks)
    selected_ids = [c.evidence_id for c in selected]

    # ev-2 should be deduplicated (same msg_id, start, end as ev-1)
    assert "ev-2" not in selected_ids, "Duplicate (msg_id, start, end) should be removed"

    # ev-1, ev-3, ev-4 should all be included (different keys)
    assert "ev-1" in selected_ids, "First chunk should be selected"
    assert "ev-3" in selected_ids, "Different start/end should not be deduplicated"
    assert "ev-4" in selected_ids, "Different msg_id should not be deduplicated"


def test_min_bucket_with_tight_token_budget():
    """Test minimum bucket guarantees work even with tight token budget."""
    selector = ContextSelector()

    # Create scenario: tight budget, but should still include at least 1 deadline
    chunks = [
        # Large chunk without deadline
        make_chunk("ev-1", "msg-1", priority_score=10.0, token_count=2800),
        # Small deadline chunk - should fit even if budget is exceeded slightly
        make_chunk(
            "ev-deadline",
            "msg-deadline",
            priority_score=0.1,
            dates=["2024-12-31"],
            token_count=300,
        ),
    ]

    # Select context
    selected = selector.select_context(chunks)
    selected_ids = [c.evidence_id for c in selected]

    # Deadline should be included (min 1 guarantee)
    assert (
        "ev-deadline" in selected_ids
    ), "Deadline chunk must be included even with tight budget (min 1 guarantee)"

    metrics = selector.get_metrics()
    assert metrics["selected_by_bucket"]["dates_deadlines"] >= 1


def test_no_deadline_chunks_available():
    """Test behavior when no deadline chunks are available."""
    selector = ContextSelector()

    # Only chunks without deadlines
    chunks = [
        make_chunk("ev-1", "msg-1", priority_score=10.0),
        make_chunk("ev-2", "msg-2", priority_score=9.0),
    ]

    # Select context
    selected = selector.select_context(chunks)

    # Should not crash, just select normally
    assert len(selected) > 0

    metrics = selector.get_metrics()
    # dates_deadlines bucket should be 0 (no deadline chunks available)
    assert metrics["selected_by_bucket"]["dates_deadlines"] == 0


def test_multiple_deadlines_sorted_by_score():
    """Test that with multiple deadlines, they are selected by score after min 1."""
    selector = ContextSelector()

    # Multiple deadline chunks with different scores
    chunks = [
        make_chunk("ev-d1", "msg-d1", priority_score=5.0, dates=["2024-12-31"]),
        make_chunk("ev-d2", "msg-d2", priority_score=8.0, dates=["2024-11-30"]),
        make_chunk("ev-d3", "msg-d3", priority_score=3.0, dates=["2024-10-15"]),
    ]

    # Select context
    selected = selector.select_context(chunks)
    selected_ids = [c.evidence_id for c in selected]

    # At least 1 should be selected
    deadline_selected = [eid for eid in selected_ids if eid.startswith("ev-d")]
    assert len(deadline_selected) >= 1, "At least 1 deadline should be selected"

    # Higher scored deadlines should be preferred
    if len(deadline_selected) > 1:
        # ev-d2 (score 8.0) should be selected before ev-d3 (score 3.0)
        assert "ev-d2" in deadline_selected


def test_dedup_key_function():
    """Test _get_dedup_key function works correctly."""
    selector = ContextSelector()

    chunk1 = make_chunk("ev-1", "msg-1", start=0, end=100)
    chunk2 = make_chunk("ev-2", "msg-1", start=0, end=100)  # Same key
    chunk3 = make_chunk("ev-3", "msg-1", start=100, end=200)  # Different key

    key1 = selector._get_dedup_key(chunk1)
    key2 = selector._get_dedup_key(chunk2)
    key3 = selector._get_dedup_key(chunk3)

    assert key1 == key2, "Same (msg_id, start, end) should produce same key"
    assert key1 != key3, "Different (start, end) should produce different key"
    assert key1 == ("msg-1", 0, 100)
    assert key3 == ("msg-1", 100, 200)


def test_both_min_guarantees_together():
    """Test that both addressed_to_me and dates_deadlines minimums work together."""
    selector = ContextSelector()

    # Low score chunks with special attributes
    chunks = [
        # High priority regular chunks
        make_chunk("ev-1", "msg-1", priority_score=10.0, token_count=100),
        make_chunk("ev-2", "msg-2", priority_score=9.0, token_count=100),
        # Low priority deadline
        make_chunk(
            "ev-deadline",
            "msg-deadline",
            priority_score=0.2,
            dates=["2024-12-31"],
            token_count=100,
        ),
        # Low priority addressed to me
        make_chunk(
            "ev-tome",
            "msg-tome",
            priority_score=0.1,
            addressed_to_me=True,
            token_count=100,
        ),
    ]

    # Select context
    selected = selector.select_context(chunks)
    selected_ids = [c.evidence_id for c in selected]

    # Both low priority special chunks should be included
    assert "ev-deadline" in selected_ids, "Deadline must be included (min 1)"
    assert "ev-tome" in selected_ids, "addressed_to_me must be included (min 1)"

    metrics = selector.get_metrics()
    assert metrics["selected_by_bucket"]["dates_deadlines"] >= 1
    assert metrics["selected_by_bucket"]["addressed_to_me"] >= 1
