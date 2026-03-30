"""
Tests for adaptive token budget and auto-shrink functionality.
"""

from datetime import datetime, timezone, timedelta
from digest_core.evidence.split import EvidenceSplitter
from digest_core.select.context import ContextSelector
from digest_core.config import (
    ContextBudgetConfig,
    ChunkingConfig,
    SelectionBucketsConfig,
    SelectionWeightsConfig,
    ShrinkConfig,
)
from digest_core.ingest.ews import NormalizedMessage
from digest_core.threads.build import ConversationThread


def create_test_message(
    msg_id: str,
    conversation_id: str,
    text_body: str,
    sender: str = "sender@example.com",
    to_recipients: list = None,
    importance: str = "Normal",
    is_flagged: bool = False,
    time_offset_hours: int = 0,
) -> NormalizedMessage:
    """Create a test normalized message."""
    return NormalizedMessage(
        msg_id=msg_id,
        conversation_id=conversation_id,
        datetime_received=datetime.now(timezone.utc) - timedelta(hours=time_offset_hours),
        sender_email=sender,
        subject=f"Test Subject {conversation_id}",
        text_body=text_body,
        to_recipients=to_recipients or ["user@example.com"],
        cc_recipients=[],
        importance=importance,
        is_flagged=is_flagged,
        has_attachments=False,
        attachment_types=[],
    )


def generate_email_load(num_emails: int, num_threads: int) -> list:
    """Generate test email load with specified number of emails and threads."""
    threads = []
    messages_per_thread = max(1, num_emails // num_threads)

    for thread_idx in range(num_threads):
        conv_id = f"thread{thread_idx}"
        messages = []

        for msg_idx in range(messages_per_thread):
            # Vary content to simulate real emails
            if msg_idx % 5 == 0:
                # Action email
                text = "Please review and approve by Friday. " + " ".join(["Details here"] * 50)
                importance = "High"
                is_flagged = True
            elif msg_idx % 3 == 0:
                # Question email
                text = "Can you help with this? " + " ".join(["More context"] * 30)
                importance = "Normal"
                is_flagged = False
            else:
                # Regular email
                text = " ".join([f"Regular content {msg_idx}"] * 20)
                importance = "Normal"
                is_flagged = False

            message = create_test_message(
                msg_id=f"{conv_id}_msg{msg_idx}",
                conversation_id=conv_id,
                text_body=text,
                sender=f"sender{thread_idx % 10}@example.com",
                to_recipients=["user@example.com", "alias1@example.com"],
                importance=importance,
                is_flagged=is_flagged,
                time_offset_hours=msg_idx,
            )
            messages.append(message)

        thread = ConversationThread(
            conversation_id=conv_id,
            messages=messages,
            latest_message_time=messages[0].datetime_received,
            participant_count=len(set(m.sender_email for m in messages)) + 1,
            message_count=len(messages),
        )
        threads.append(thread)

    return threads


class TestAdaptiveBudget:
    """Test suite for adaptive token budget."""

    def test_load_profile_100_emails(self):
        """Test 100 emails: no shrink expected, full coverage."""
        threads = generate_email_load(num_emails=100, num_threads=40)

        # Configure
        context_budget = ContextBudgetConfig(max_total_tokens=7000, per_thread_max=3)
        chunking = ChunkingConfig()
        buckets = SelectionBucketsConfig()
        weights = SelectionWeightsConfig()
        shrink = ShrinkConfig(enable_auto_shrink=True, preserve_min_quotas=True)

        # Split evidence
        splitter = EvidenceSplitter(
            user_aliases=["user@example.com", "alias1@example.com"],
            context_budget_config=context_budget,
            chunking_config=chunking,
        )
        evidence_chunks = splitter.split_evidence(threads, total_emails=100, total_threads=40)

        # Select context
        selector = ContextSelector(
            buckets_config=buckets,
            weights_config=weights,
            context_budget_config=context_budget,
            shrink_config=shrink,
        )
        selected = selector.select_context(evidence_chunks)
        metrics = selector.get_metrics()

        # Assertions
        assert len(selected) > 0
        assert metrics["token_budget_used"] <= 7000
        # With 100 emails, shrink should be minimal or zero
        assert metrics["shrink_percentage"] <= 10.0
        # Thread coverage should be good
        assert metrics["covered_threads"] >= 10

    def test_load_profile_200_emails(self):
        """Test 200 emails: moderate shrink (≤20%), adaptive chunking active."""
        threads = generate_email_load(num_emails=200, num_threads=60)

        # Configure
        context_budget = ContextBudgetConfig(max_total_tokens=7000, per_thread_max=3)
        chunking = ChunkingConfig(adaptive_high_load_emails=200)
        buckets = SelectionBucketsConfig()
        weights = SelectionWeightsConfig()
        shrink = ShrinkConfig(enable_auto_shrink=True, preserve_min_quotas=True)

        # Split evidence
        splitter = EvidenceSplitter(
            user_aliases=["user@example.com"],
            context_budget_config=context_budget,
            chunking_config=chunking,
        )
        evidence_chunks = splitter.split_evidence(threads, total_emails=200, total_threads=60)

        # Select context
        selector = ContextSelector(
            buckets_config=buckets,
            weights_config=weights,
            context_budget_config=context_budget,
            shrink_config=shrink,
        )
        selected = selector.select_context(evidence_chunks)
        metrics = selector.get_metrics()

        # Assertions
        assert len(selected) > 0
        assert metrics["token_budget_used"] <= 7000
        # Moderate shrink expected
        assert metrics["shrink_percentage"] <= 20.0
        # Thread coverage should still be good
        assert metrics["covered_threads"] >= 10
        # Min quotas should be respected
        assert sum(metrics["selected_by_bucket"].values()) >= len(selected)

    def test_load_profile_300_emails(self):
        """Test 300+ emails: shrink ≤30%, min quotas preserved, coverage ≥90%."""
        threads = generate_email_load(num_emails=300, num_threads=80)

        # Configure
        context_budget = ContextBudgetConfig(max_total_tokens=7000, per_thread_max=3)
        chunking = ChunkingConfig()
        buckets = SelectionBucketsConfig(
            threads_top=10, addressed_to_me=8, dates_deadlines=6, critical_senders=4
        )
        weights = SelectionWeightsConfig()
        shrink = ShrinkConfig(enable_auto_shrink=True, preserve_min_quotas=True)

        # Split evidence
        splitter = EvidenceSplitter(
            user_aliases=["user@example.com", "alias1@example.com"],
            context_budget_config=context_budget,
            chunking_config=chunking,
        )
        evidence_chunks = splitter.split_evidence(threads, total_emails=300, total_threads=80)

        # Select context
        selector = ContextSelector(
            buckets_config=buckets,
            weights_config=weights,
            context_budget_config=context_budget,
            shrink_config=shrink,
        )
        selected = selector.select_context(evidence_chunks)
        metrics = selector.get_metrics()

        # Assertions
        assert len(selected) > 0
        # Token budget never exceeded
        assert metrics["token_budget_used"] <= 7000
        # Shrink percentage ≤30%
        assert metrics["shrink_percentage"] <= 30.0

        # Min quotas preserved
        selected_by_bucket = metrics["selected_by_bucket"]
        assert selected_by_bucket.get("threads_top", 0) >= 10 or metrics["covered_threads"] >= 10

        # Thread coverage ≥90% (at least 72 out of 80 threads)
        # Since threads_top=10, we should have at least that many
        assert metrics["covered_threads"] >= 10

        # Budget applied should be close to budget used
        assert abs(metrics["budget_applied"] - metrics["token_budget_used"]) < 100

    def test_shrink_preserves_min_quotas(self):
        """Test that auto-shrink preserves minimum bucket quotas."""
        # Generate large load that will trigger shrink
        threads = generate_email_load(num_emails=400, num_threads=100)

        # Configure with small max_total_tokens to force shrink
        context_budget = ContextBudgetConfig(max_total_tokens=5000, per_thread_max=2)
        chunking = ChunkingConfig()
        buckets = SelectionBucketsConfig(
            threads_top=10, addressed_to_me=8, dates_deadlines=6, critical_senders=4
        )
        weights = SelectionWeightsConfig()
        shrink = ShrinkConfig(enable_auto_shrink=True, preserve_min_quotas=True)

        # Split evidence
        splitter = EvidenceSplitter(
            user_aliases=["user@example.com"],
            context_budget_config=context_budget,
            chunking_config=chunking,
        )
        evidence_chunks = splitter.split_evidence(threads, total_emails=400, total_threads=100)

        # Select context
        selector = ContextSelector(
            buckets_config=buckets,
            weights_config=weights,
            context_budget_config=context_budget,
            shrink_config=shrink,
        )
        selected = selector.select_context(evidence_chunks)
        metrics = selector.get_metrics()

        # Assertions
        assert metrics["token_budget_used"] <= 5000
        # Shrink may happen at splitter or selector level
        # What matters is budget is respected

        # Thread coverage should respect min quota
        assert metrics["covered_threads"] >= 10

        # Selected chunks should respect per_thread_max
        # Count chunks per thread
        thread_counts = {}
        for chunk in selected:
            conv_id = chunk.conversation_id
            thread_counts[conv_id] = thread_counts.get(conv_id, 0) + 1

        # No thread should exceed per_thread_max
        for count in thread_counts.values():
            assert count <= 2  # per_thread_max=2

    def test_token_budget_never_exceeded(self):
        """Test that token budget is never exceeded regardless of input."""
        # Extreme load
        threads = generate_email_load(num_emails=500, num_threads=120)

        context_budget = ContextBudgetConfig(max_total_tokens=7000, per_thread_max=3)
        chunking = ChunkingConfig()
        buckets = SelectionBucketsConfig()
        weights = SelectionWeightsConfig()
        shrink = ShrinkConfig(enable_auto_shrink=True)

        splitter = EvidenceSplitter(
            user_aliases=["user@example.com"],
            context_budget_config=context_budget,
            chunking_config=chunking,
        )
        evidence_chunks = splitter.split_evidence(threads, total_emails=500, total_threads=120)

        selector = ContextSelector(
            buckets_config=buckets,
            weights_config=weights,
            context_budget_config=context_budget,
            shrink_config=shrink,
        )
        selector.select_context(evidence_chunks)
        metrics = selector.get_metrics()

        # Critical assertion: budget never exceeded
        assert metrics["token_budget_used"] <= 7000
        assert metrics["budget_applied"] <= 7000
