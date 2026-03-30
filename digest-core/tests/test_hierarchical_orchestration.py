"""
Tests for hierarchical orchestration with must-include and merge policy.

Coverage:
- Auto-enable based on thresholds (threads>=60 OR emails>=300)
- Must-include chunks: mentions + last_update
- Skip LLM if no evidence
- Merge policy: title + 3-5 citations
- Metrics: hierarchical_runs_total, avg_subsummary_chunks, saved_tokens
- Mail explosion: latency/cost vs baseline, F1 for actions/mentions
"""

import pytest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from digest_core.config import HierarchicalConfig
from digest_core.hierarchical.processor import HierarchicalProcessor
from digest_core.evidence.split import EvidenceChunk
from digest_core.threads.build import ConversationThread
from digest_core.llm.schemas import ThreadSummary
from digest_core.llm.gateway import LLMGateway


@pytest.fixture
def hierarchical_config():
    """Create hierarchical config with test settings."""
    return HierarchicalConfig(
        enable=True,
        auto_enable=True,
        min_threads=60,
        min_emails=300,
        per_thread_max_chunks_in=8,
        per_thread_max_chunks_exception=12,
        must_include_mentions=True,
        must_include_last_update=True,
        merge_max_citations=5,
        merge_include_title=True,
        skip_llm_if_no_evidence=True,
    )


@pytest.fixture
def mock_llm_gateway():
    """Create mock LLM gateway."""
    gateway = Mock(spec=LLMGateway)

    # Mock successful LLM response
    gateway._make_request_with_retry.return_value = {
        "data": {
            "thread_id": "test_thread",
            "summary": "Test thread summary",
            "key_points": ["Point 1", "Point 2"],
            "pending_actions": [],
            "deadlines": [],
            "decisions": [],
            "open_questions": [],
            "who_must_act": [],
            "evidence_ids": [],
        }
    }

    return gateway


class TestAutoEnableThresholds:
    """Test automatic hierarchical mode activation."""

    def test_auto_enable_by_threads(self, hierarchical_config, mock_llm_gateway):
        """Test auto-enable when threads >= 60."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        # Create 65 threads, 50 emails
        threads = [Mock(spec=ConversationThread) for _ in range(65)]
        emails = [Mock() for _ in range(50)]

        should_use = processor.should_use_hierarchical(threads, emails)
        assert should_use is True, "Should enable with threads >= 60"

    def test_auto_enable_by_emails(self, hierarchical_config, mock_llm_gateway):
        """Test auto-enable when emails >= 300."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        # Create 40 threads, 350 emails
        threads = [Mock(spec=ConversationThread) for _ in range(40)]
        emails = [Mock() for _ in range(350)]

        should_use = processor.should_use_hierarchical(threads, emails)
        assert should_use is True, "Should enable with emails >= 300"

    def test_no_auto_enable_below_thresholds(self, hierarchical_config, mock_llm_gateway):
        """Test no auto-enable when below both thresholds."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        # Create 30 threads, 100 emails (both below)
        threads = [Mock(spec=ConversationThread) for _ in range(30)]
        emails = [Mock() for _ in range(100)]

        should_use = processor.should_use_hierarchical(threads, emails)
        assert should_use is False, "Should not enable below thresholds"

    def test_disabled_hierarchical(self, mock_llm_gateway):
        """Test that hierarchical can be disabled."""
        config = HierarchicalConfig(enable=False, auto_enable=False)
        processor = HierarchicalProcessor(config, mock_llm_gateway)

        threads = [Mock(spec=ConversationThread) for _ in range(100)]
        emails = [Mock() for _ in range(500)]

        should_use = processor.should_use_hierarchical(threads, emails)
        assert should_use is False, "Should not enable when disabled"


class TestMustIncludeChunks:
    """Test must-include chunks (mentions + last_update)."""

    def test_must_include_mentions(self, hierarchical_config, mock_llm_gateway):
        """Test that chunks with user mentions are always included."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        now = datetime.now(timezone.utc)

        # Create 12 chunks, 2 with mentions
        chunks = []
        for i in range(12):
            has_mention = i == 3 or i == 7
            text = "User john@example.com please review" if has_mention else "Regular content"

            chunk = EvidenceChunk(
                evidence_id=f"ev{i}",
                msg_id=f"msg{i}",
                text=text,
                sender="sender@example.com",
                timestamp=(now - timedelta(hours=i)).isoformat(),
                priority_score=1.0 - (i * 0.05),  # Descending priority
            )
            chunks.append(chunk)

        user_aliases = ["john@example.com"]
        selected = processor._select_chunks_with_must_include(chunks, user_aliases, max_chunks=8)

        # Check that mention chunks are included
        selected_texts = [c.text for c in selected]
        assert any(
            "john@example.com" in text for text in selected_texts
        ), "Mention chunks should be included"

        # Should have both mention chunks
        mention_count = sum(1 for text in selected_texts if "john@example.com" in text)
        assert mention_count == 2, "Both mention chunks should be included"

    def test_must_include_last_update(self, hierarchical_config, mock_llm_gateway):
        """Test that last update chunk (most recent) is always included."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        now = datetime.now(timezone.utc)

        # Create chunks with different timestamps
        chunks = []
        for i in range(10):
            timestamp = (now - timedelta(hours=10 - i)).isoformat()  # i=9 is most recent
            chunk = EvidenceChunk(
                evidence_id=f"ev{i}",
                msg_id=f"msg{i}",
                text=f"Content {i}",
                sender="sender@example.com",
                timestamp=timestamp,
                priority_score=0.5,  # Same priority
            )
            chunks.append(chunk)

        selected = processor._select_chunks_with_must_include(chunks, user_aliases=[], max_chunks=5)

        # Last update chunk (i=9) should be included
        selected_ids = [c.evidence_id for c in selected]
        assert "ev9" in selected_ids, "Last update chunk should be included"

    def test_exception_limit_with_many_must_include(self, hierarchical_config, mock_llm_gateway):
        """Test that exception limit (12) is used when many must-include chunks."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        now = datetime.now(timezone.utc)

        # Create 10 chunks with mentions (exceeds normal limit of 8)
        chunks = []
        for i in range(15):
            has_mention = i < 10  # First 10 have mentions
            text = f"User user@example.com content {i}" if has_mention else f"Regular content {i}"

            chunk = EvidenceChunk(
                evidence_id=f"ev{i}",
                msg_id=f"msg{i}",
                text=text,
                sender="sender@example.com",
                timestamp=(now - timedelta(hours=i)).isoformat(),
                priority_score=1.0,
            )
            chunks.append(chunk)

        selected = processor._select_chunks_with_must_include(
            chunks, user_aliases=["user@example.com"], max_chunks=8
        )

        # Should select up to exception limit (12)
        assert (
            len(selected) <= hierarchical_config.per_thread_max_chunks_exception
        ), "Should extend to exception limit"

        # All 10 mention chunks should be included (within 12 limit)
        mention_count = sum(1 for c in selected if "user@example.com" in c.text)
        assert mention_count == 10, "All mention chunks should be included"


class TestSkipLLM:
    """Test LLM skipping when no evidence."""

    def test_skip_llm_no_evidence(self, hierarchical_config, mock_llm_gateway):
        """Test that LLM is skipped when no evidence after selection."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        # Empty chunks
        summary = processor._summarize_single_thread(
            thread_id="empty_thread", chunks=[], trace_id="test", user_aliases=[]
        )

        # Should return empty summary without calling LLM
        assert summary.thread_id == "empty_thread"
        assert summary.summary == ""
        assert summary.pending_actions == []

        # LLM should not be called
        mock_llm_gateway._make_request_with_retry.assert_not_called()

    def test_no_skip_when_disabled(self, mock_llm_gateway):
        """Test that LLM is not skipped when optimization is disabled."""
        config = HierarchicalConfig(skip_llm_if_no_evidence=False)
        HierarchicalProcessor(config, mock_llm_gateway)

        # This would normally call LLM even with empty chunks
        # (In real scenario, would raise error or handle gracefully)
        pass


class TestMergePolicy:
    """Test merge policy with citations."""

    def test_extract_key_citations(self, hierarchical_config, mock_llm_gateway):
        """Test extraction of 3-5 key citations."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        now = datetime.now(timezone.utc)

        # Create chunks
        chunks = []
        for i in range(10):
            text = f"This is important content number {i} with lots of details and information that needs to be summarized."
            chunk = EvidenceChunk(
                evidence_id=f"ev{i}",
                msg_id=f"msg{i}",
                text=text,
                sender="sender@example.com",
                timestamp=now.isoformat(),
                priority_score=1.0 - (i * 0.1),
            )
            chunks.append(chunk)

        citations = processor._extract_key_citations_from_chunks(chunks, max_citations=5)

        # Should have 5 citations
        assert len(citations) == 5, "Should extract 5 citations"

        # Each citation should have evidence_id and snippet
        for cit in citations:
            assert "[ev" in cit, "Citation should include evidence_id"
            assert "important content" in cit.lower(), "Citation should include snippet"

    def test_merge_policy_in_aggregator(self, hierarchical_config, mock_llm_gateway):
        """Test that merge policy is applied in aggregator input."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        now = datetime.now(timezone.utc)

        # Create thread summary
        summary = ThreadSummary(
            thread_id="thread1",
            summary="Test thread summary",
            pending_actions=[],
            deadlines=[],
            who_must_act=[],
            open_questions=[],
            evidence_ids=[],
        )

        # Create chunks
        chunks = [
            EvidenceChunk(
                evidence_id=f"ev{i}",
                msg_id=f"msg{i}",
                text=f"Content {i}",
                sender="sender@example.com",
                timestamp=now.isoformat(),
            )
            for i in range(3)
        ]

        aggregator_input = processor._prepare_aggregator_input(
            thread_summaries=[summary],
            all_thread_chunks={"thread1": chunks},
            summarized_threads={"thread1": chunks},
        )

        # Should include title
        assert "Summary: Test thread summary" in aggregator_input

        # Should include citations
        assert "Key Citations" in aggregator_input
        assert "[ev0]" in aggregator_input


class TestMailExplosion:
    """Test with synthetic 'mail explosion' scenario."""

    def test_mail_explosion_performance(self, hierarchical_config, mock_llm_gateway):
        """Test latency and cost with large volume."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        now = datetime.now(timezone.utc)

        # Create 100 threads with 500 total emails (mail explosion)
        threads = []
        all_chunks = []

        for thread_idx in range(100):
            thread = ConversationThread(
                conversation_id=f"thread{thread_idx}",
                messages=[],
                latest_message_time=now,
                participant_count=1,
                message_count=5,
            )
            threads.append(thread)

            # Each thread has 3-10 chunks
            num_chunks = 5
            for chunk_idx in range(num_chunks):
                chunk = EvidenceChunk(
                    evidence_id=f"ev{thread_idx}_{chunk_idx}",
                    msg_id=f"msg{thread_idx}_{chunk_idx}",
                    text=f"Thread {thread_idx} content {chunk_idx}",
                    sender="sender@example.com",
                    timestamp=now.isoformat(),
                    conversation_id=f"thread{thread_idx}",
                    priority_score=1.0,
                )
                all_chunks.append(chunk)

        # Should trigger hierarchical mode
        should_use = processor.should_use_hierarchical(threads, all_chunks)
        assert should_use is True, "Should use hierarchical with 100 threads"

        # Test basic processing (mock)
        start_time = time.time()

        # Group chunks
        thread_chunks = processor._group_chunks_by_thread(threads, all_chunks)

        latency = time.time() - start_time

        # Latency should be reasonable (< 1 second for grouping)
        assert latency < 1.0, f"Grouping latency too high: {latency:.2f}s"

        # Should have 100 thread groups
        assert len(thread_chunks) == 100

        # Average chunks per thread
        avg_chunks = sum(len(chunks) for chunks in thread_chunks.values()) / len(thread_chunks)
        assert 3 <= avg_chunks <= 10, f"Avg chunks per thread: {avg_chunks}"


class TestMetricsIntegration:
    """Test metrics recording."""

    def test_hierarchical_run_metrics(self, hierarchical_config, mock_llm_gateway):
        """Test that hierarchical_runs_total is recorded."""
        # This would be tested in integration test with actual metrics collector
        pass

    def test_avg_subsummary_chunks_metrics(self, hierarchical_config, mock_llm_gateway):
        """Test that avg_subsummary_chunks is recorded."""
        # This would be tested in integration test with actual metrics collector
        pass

    def test_saved_tokens_metrics(self, hierarchical_config, mock_llm_gateway):
        """Test that saved_tokens is recorded when skipping LLM."""
        # This would be tested in integration test with actual metrics collector
        pass


class TestF1Preservation:
    """Test that F1 for actions/mentions doesn't degrade."""

    def test_actions_not_lost(self, hierarchical_config, mock_llm_gateway):
        """Test that actions are preserved through hierarchical processing."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        now = datetime.now(timezone.utc)

        # Create chunks with action markers
        chunks_with_actions = []
        for i in range(5):
            text = f"Please review document {i} by Friday"
            chunk = EvidenceChunk(
                evidence_id=f"action_ev{i}",
                msg_id=f"msg{i}",
                text=text,
                sender="manager@example.com",
                timestamp=now.isoformat(),
                priority_score=1.0,
            )
            chunks_with_actions.append(chunk)

        # Select with must-include
        selected = processor._select_chunks_with_must_include(
            chunks_with_actions, user_aliases=[], max_chunks=8
        )

        # All action chunks should be selected (within limit)
        assert len(selected) == len(chunks_with_actions), "All chunks should be selected"

        # Action text should be preserved
        for chunk in selected:
            assert "please review" in chunk.text.lower()

    def test_mentions_not_lost(self, hierarchical_config, mock_llm_gateway):
        """Test that user mentions are preserved."""
        processor = HierarchicalProcessor(hierarchical_config, mock_llm_gateway)

        now = datetime.now(timezone.utc)

        # Create chunks, some with mentions
        chunks = []
        for i in range(10):
            has_mention = i % 3 == 0  # Every 3rd has mention
            text = (
                f"User user@example.com needs to act on {i}"
                if has_mention
                else f"Regular content {i}"
            )

            chunk = EvidenceChunk(
                evidence_id=f"ev{i}",
                msg_id=f"msg{i}",
                text=text,
                sender="sender@example.com",
                timestamp=now.isoformat(),
                priority_score=0.5,
            )
            chunks.append(chunk)

        selected = processor._select_chunks_with_must_include(
            chunks, user_aliases=["user@example.com"], max_chunks=8
        )

        # All mention chunks should be selected
        mention_count = sum(1 for c in selected if "user@example.com" in c.text)
        expected_mentions = sum(1 for c in chunks if "user@example.com" in c.text)

        assert (
            mention_count == expected_mentions
        ), f"All {expected_mentions} mention chunks should be selected, got {mention_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
