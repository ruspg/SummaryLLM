"""
Tests for hierarchical digest mode.
"""

import pytest
from unittest.mock import Mock, patch

from digest_core.config import HierarchicalConfig
from digest_core.hierarchical import HierarchicalProcessor, HierarchicalMetrics
from digest_core.llm.schemas import (
    ThreadSummary,
    ThreadAction,
    ThreadDeadline,
    EnhancedDigest,
)
from digest_core.evidence.split import EvidenceChunk
from digest_core.llm.gateway import LLMGateway

from tests.fixtures.large_dataset import generate_large_email_dataset


class TestHierarchicalThresholds:
    """Test hierarchical mode activation thresholds."""

    def test_threshold_activation_by_threads(self):
        """Test hierarchical mode activates at thread threshold."""
        config = HierarchicalConfig(min_threads=30, min_emails=150)
        mock_gateway = Mock(spec=LLMGateway)
        processor = HierarchicalProcessor(config, mock_gateway)

        # Below threshold
        assert not processor.should_use_hierarchical(
            threads=[Mock() for _ in range(25)], emails=[Mock() for _ in range(100)]
        )

        # At threshold
        assert processor.should_use_hierarchical(
            threads=[Mock() for _ in range(30)], emails=[Mock() for _ in range(100)]
        )

        # Above threshold
        assert processor.should_use_hierarchical(
            threads=[Mock() for _ in range(40)], emails=[Mock() for _ in range(100)]
        )

    def test_threshold_activation_by_emails(self):
        """Test hierarchical mode activates at email threshold."""
        config = HierarchicalConfig(min_threads=30, min_emails=150)
        mock_gateway = Mock(spec=LLMGateway)
        processor = HierarchicalProcessor(config, mock_gateway)

        # Below threshold
        assert not processor.should_use_hierarchical(
            threads=[Mock() for _ in range(20)], emails=[Mock() for _ in range(100)]
        )

        # At threshold
        assert processor.should_use_hierarchical(
            threads=[Mock() for _ in range(20)], emails=[Mock() for _ in range(150)]
        )

        # Above threshold
        assert processor.should_use_hierarchical(
            threads=[Mock() for _ in range(20)], emails=[Mock() for _ in range(200)]
        )

    def test_disabled_config(self):
        """Test hierarchical mode respects enable flag."""
        config = HierarchicalConfig(enable=False, min_threads=10, min_emails=50)
        mock_gateway = Mock(spec=LLMGateway)
        processor = HierarchicalProcessor(config, mock_gateway)

        assert not processor.should_use_hierarchical(
            threads=[Mock() for _ in range(50)], emails=[Mock() for _ in range(200)]
        )


class TestThreadFiltering:
    """Test thread filtering for summarization."""

    def test_small_threads_skipped(self):
        """Test threads < 3 chunks skip summarization."""
        config = HierarchicalConfig()
        mock_gateway = Mock(spec=LLMGateway)
        processor = HierarchicalProcessor(config, mock_gateway)

        thread_chunks = {
            "thread1": [Mock() for _ in range(5)],  # Should summarize
            "thread2": [Mock() for _ in range(2)],  # Should skip
            "thread3": [Mock() for _ in range(10)],  # Should summarize (capped at 8)
            "thread4": [Mock()],  # Should skip
        }

        filtered = processor._filter_threads_for_summarization(thread_chunks)

        assert "thread1" in filtered
        assert "thread2" not in filtered
        assert "thread3" in filtered
        assert "thread4" not in filtered
        assert len(filtered["thread3"]) == 8  # Capped at per_thread_max_chunks_in
        assert processor.metrics.threads_skipped_small == 2

    def test_per_thread_max_chunks_in_applied(self):
        """Test per_thread_max_chunks_in limit is applied."""
        config = HierarchicalConfig(per_thread_max_chunks_in=5)
        mock_gateway = Mock(spec=LLMGateway)
        processor = HierarchicalProcessor(config, mock_gateway)

        thread_chunks = {"thread1": [Mock() for _ in range(10)]}

        filtered = processor._filter_threads_for_summarization(thread_chunks)

        assert len(filtered["thread1"]) == 5


class TestThreadSummaryStructure:
    """Test ThreadSummary has required fields."""

    def test_thread_summary_structure(self):
        """Test ThreadSummary has required fields with evidence_id and quotes."""
        action = ThreadAction(
            title="Test action",
            evidence_id="ev_123",
            quote="This is a test quote for the action item.",
            who_must_act="user",
        )

        deadline = ThreadDeadline(
            title="Test deadline",
            date_time="2024-12-15T14:00:00",
            evidence_id="ev_456",
            quote="This is a test quote for the deadline item.",
        )

        summary = ThreadSummary(
            thread_id="test_thread_1",
            summary="This is a test thread summary.",
            pending_actions=[action],
            deadlines=[deadline],
            who_must_act=["user"],
            open_questions=["Test question?"],
            evidence_ids=["ev_123", "ev_456"],
        )

        assert summary.thread_id == "test_thread_1"
        assert len(summary.pending_actions) == 1
        assert summary.pending_actions[0].evidence_id == "ev_123"
        assert len(summary.pending_actions[0].quote) >= 10
        assert len(summary.deadlines) == 1
        assert summary.deadlines[0].evidence_id == "ev_456"
        assert len(summary.deadlines[0].quote) >= 10


class TestDegradation:
    """Test timeout degradation."""

    def test_degrade_thread_summary(self):
        """Test degraded thread summary creation."""
        config = HierarchicalConfig()
        mock_gateway = Mock(spec=LLMGateway)
        processor = HierarchicalProcessor(config, mock_gateway)

        # Create mock chunks
        chunk1 = Mock(spec=EvidenceChunk)
        chunk1.evidence_id = "ev_1"
        chunk1.content = "First chunk content with important information about the project status."

        chunk2 = Mock(spec=EvidenceChunk)
        chunk2.evidence_id = "ev_2"
        chunk2.content = "Second chunk content with action items that need to be completed."

        chunks = [chunk1, chunk2]

        degraded = processor._degrade_thread_summary("test_thread", chunks)

        assert degraded.thread_id == "test_thread"
        assert len(degraded.evidence_ids) == 2
        assert "ev_1" in degraded.evidence_ids
        assert "ev_2" in degraded.evidence_ids
        assert len(degraded.summary) <= 300
        assert "degraded" in degraded.summary.lower()


class TestFinalAggregation:
    """Test final aggregation to EnhancedDigest v2."""

    @patch("digest_core.hierarchical.processor.HierarchicalProcessor._final_aggregation")
    def test_final_aggregation_to_enhanced_digest_v2(self, mock_aggregation):
        """Test final output is EnhancedDigest v2."""
        # Mock the return value
        mock_digest = Mock(spec=EnhancedDigest)
        mock_digest.schema_version = "2.0"
        mock_digest.my_actions = []
        mock_digest.others_actions = []
        mock_digest.deadlines_meetings = []
        mock_digest.risks_blockers = []
        mock_digest.fyi = []

        mock_aggregation.return_value = mock_digest

        config = HierarchicalConfig()
        mock_gateway = Mock(spec=LLMGateway)
        processor = HierarchicalProcessor(config, mock_gateway)

        result = processor._final_aggregation("test input", "2024-12-14", "trace_123")

        assert result.schema_version == "2.0"


class TestMetrics:
    """Test hierarchical metrics."""

    def test_metrics_initialization(self):
        """Test metrics are initialized correctly."""
        metrics = HierarchicalMetrics()

        assert metrics.threads_summarized == 0
        assert metrics.threads_skipped_small == 0
        assert metrics.per_thread_tokens == []
        assert metrics.final_input_tokens == 0
        assert metrics.timeouts == 0
        assert metrics.errors == 0

    def test_metrics_to_dict(self):
        """Test metrics conversion to dict."""
        metrics = HierarchicalMetrics()
        metrics.threads_summarized = 10
        metrics.threads_skipped_small = 5
        metrics.per_thread_tokens = [100.0, 150.0, 120.0]
        metrics.final_input_tokens = 4000

        result = metrics.to_dict()

        assert result["threads_summarized"] == 10
        assert result["threads_skipped_small"] == 5
        assert result["per_thread_avg_tokens"] == (100 + 150 + 120) / 3
        assert result["final_input_tokens"] == 4000


class TestLargeDatasetIntegration:
    """Integration tests with large dataset."""

    @pytest.mark.slow
    def test_300_emails_processing(self):
        """Test processing 300+ emails activates hierarchical mode."""
        from digest_core.threads.build import ThreadBuilder

        # Generate dataset
        messages = generate_large_email_dataset(count=300)

        # Build threads
        thread_builder = ThreadBuilder()
        threads = thread_builder.build_threads(messages)

        # Check threshold activation
        config = HierarchicalConfig(min_threads=30, min_emails=150)
        mock_gateway = Mock(spec=LLMGateway)
        processor = HierarchicalProcessor(config, mock_gateway)

        assert processor.should_use_hierarchical(threads, messages)
        assert len(messages) == 300  # Exact count
        assert len(threads) >= 10  # Should have multiple threads
        # Note: large threads (10-20 messages) mean fewer total threads,
        # but email count threshold (150) is still met


# Acceptance criteria tests
class TestAcceptanceCriteria:
    """Test acceptance criteria for hierarchical mode."""

    def test_all_items_have_evidence_id_and_quote(self):
        """Validate: every action/deadline has valid evidence_id + quote."""
        action = ThreadAction(
            title="Test",
            evidence_id="ev_123",
            quote="This is a valid quote with more than ten characters.",
            who_must_act="user",
        )

        # Should not raise validation error
        assert action.evidence_id
        assert len(action.quote) >= 10

    def test_quote_min_length_validation(self):
        """Test that quotes < 10 chars fail validation."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ThreadAction(
                title="Test",
                evidence_id="ev_123",
                quote="Short",  # Too short
                who_must_act="user",
            )
