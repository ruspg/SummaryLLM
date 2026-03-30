"""
Tests for balanced evidence selection strategy.
"""

import pytest
from datetime import datetime, timezone, timedelta

from digest_core.select.context import ContextSelector
from digest_core.evidence.split import EvidenceChunk
from digest_core.config import SelectionBucketsConfig, SelectionWeightsConfig


class TestBalancedSelection:
    """Tests for balanced bucket selection strategy."""

    def create_test_chunk(self, **kwargs):
        """Helper to create test EvidenceChunk."""
        defaults = {
            "evidence_id": "ev-test-1",
            "conversation_id": "conv-1",
            "content": "Test content",
            "source_ref": {"type": "email", "msg_id": "msg-1"},
            "token_count": 100,
            "priority_score": 5.0,
            "message_metadata": {
                "from": "sender@example.com",
                "to": ["user@example.com"],
                "cc": [],
                "subject": "Test",
                "received_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                "importance": "Normal",
                "is_flagged": False,
                "has_attachments": False,
                "attachment_types": [],
            },
            "addressed_to_me": False,
            "user_aliases_matched": [],
            "signals": {
                "action_verbs": [],
                "dates": [],
                "contains_question": False,
                "sender_rank": 1,
                "attachments": [],
            },
        }
        defaults.update(kwargs)
        return EvidenceChunk(**defaults)

    def test_noisy_thread_doesnt_consume_budget(self):
        """Test that one noisy thread doesn't consume entire budget."""
        # Create 10 chunks from the same thread
        noisy_chunks = []
        for i in range(10):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-noisy-{i}",
                conversation_id="conv-noisy",
                token_count=200,
                priority_score=10.0,  # High score
                signals={
                    "action_verbs": ["please"],
                    "dates": [],
                    "contains_question": False,
                    "sender_rank": 1,
                },
            )
            noisy_chunks.append(chunk)

        # Create 5 chunks from different threads
        diverse_chunks = []
        for i in range(5):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-diverse-{i}",
                conversation_id=f"conv-diverse-{i}",
                token_count=150,
                priority_score=8.0,
                signals={
                    "action_verbs": ["need"],
                    "dates": [],
                    "contains_question": False,
                    "sender_rank": 1,
                },
            )
            diverse_chunks.append(chunk)

        all_chunks = noisy_chunks + diverse_chunks

        # Select with per_thread_max=3
        config_buckets = SelectionBucketsConfig(per_thread_max=3, max_total_chunks=20)
        config_weights = SelectionWeightsConfig()
        selector = ContextSelector(config_buckets, config_weights)

        selected = selector.select_context(all_chunks)

        # Check that noisy thread has at most 3 chunks
        noisy_selected = [c for c in selected if c.conversation_id == "conv-noisy"]
        assert (
            len(noisy_selected) <= 3
        ), f"Noisy thread has {len(noisy_selected)} chunks, expected <= 3"

        # Check that we selected from multiple threads
        metrics = selector.get_metrics()
        assert metrics["covered_threads"] >= 3, f"Only {metrics['covered_threads']} threads covered"

        print(f"✓ Noisy thread limited to {len(noisy_selected)} chunks")
        print(f"✓ Covered {metrics['covered_threads']} different threads")

    def test_deadlines_and_tome_prioritized(self):
        """Test that chunks with deadlines and addressed_to_me are prioritized."""
        # Create chunks with deadlines
        deadline_chunks = []
        for i in range(4):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-deadline-{i}",
                conversation_id=f"conv-deadline-{i}",
                token_count=100,
                priority_score=5.0,
                signals={
                    "action_verbs": ["urgent"],
                    "dates": ["2024-12-31"],
                    "contains_question": False,
                    "sender_rank": 1,
                },
            )
            deadline_chunks.append(chunk)

        # Create chunks addressed to me
        tome_chunks = []
        for i in range(4):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-tome-{i}",
                conversation_id=f"conv-tome-{i}",
                token_count=100,
                priority_score=5.0,
                addressed_to_me=True,
                user_aliases_matched=["user@example.com"],
                signals={
                    "action_verbs": ["please"],
                    "dates": [],
                    "contains_question": False,
                    "sender_rank": 1,
                },
            )
            tome_chunks.append(chunk)

        # Create generic chunks
        generic_chunks = []
        for i in range(10):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-generic-{i}",
                conversation_id=f"conv-generic-{i}",
                token_count=100,
                priority_score=3.0,  # Lower score
                signals={
                    "action_verbs": [],
                    "dates": [],
                    "contains_question": False,
                    "sender_rank": 1,
                },
            )
            generic_chunks.append(chunk)

        all_chunks = deadline_chunks + tome_chunks + generic_chunks

        config_buckets = SelectionBucketsConfig(
            addressed_to_me=8, dates_deadlines=6, max_total_chunks=20
        )
        config_weights = SelectionWeightsConfig()
        selector = ContextSelector(config_buckets, config_weights)

        selected = selector.select_context(all_chunks)
        metrics = selector.get_metrics()

        # Check that deadline and to-me chunks are well represented
        deadline_selected = [c for c in selected if len(c.signals.get("dates", [])) > 0]
        tome_selected = [c for c in selected if c.addressed_to_me]

        print(f"✓ Selected {len(deadline_selected)} chunks with deadlines")
        print(f"✓ Selected {len(tome_selected)} chunks addressed to me")
        print(f"✓ Bucket distribution: {metrics['selected_by_bucket']}")

        assert (
            len(deadline_selected) >= 4
        ), f"Only {len(deadline_selected)} deadline chunks selected"
        assert len(tome_selected) >= 4, f"Only {len(tome_selected)} to-me chunks selected"

    def test_action_thread_coverage(self):
        """Test that ≥90% of threads with action signals are covered."""
        # Create 20 threads with action signals
        action_threads = []
        for i in range(20):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-action-{i}",
                conversation_id=f"conv-action-{i}",
                token_count=100,
                priority_score=7.0,
                signals={
                    "action_verbs": ["please", "need"],
                    "dates": ["2024-12-25"] if i % 3 == 0 else [],
                    "contains_question": i % 2 == 0,
                    "sender_rank": 1,
                },
            )
            action_threads.append(chunk)

        # Create 10 threads without action signals
        non_action_threads = []
        for i in range(10):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-nonaction-{i}",
                conversation_id=f"conv-nonaction-{i}",
                token_count=100,
                priority_score=2.0,
                signals={
                    "action_verbs": [],
                    "dates": [],
                    "contains_question": False,
                    "sender_rank": 1,
                },
            )
            non_action_threads.append(chunk)

        all_chunks = action_threads + non_action_threads

        config_buckets = SelectionBucketsConfig(threads_top=10, max_total_chunks=20)
        config_weights = SelectionWeightsConfig(
            action_verbs=2.0, dates_found=2.0  # High weight for action verbs
        )
        selector = ContextSelector(config_buckets, config_weights)

        selected = selector.select_context(all_chunks)
        metrics = selector.get_metrics()

        # Count how many action threads are covered
        action_conv_ids = {c.conversation_id for c in action_threads}
        covered_threads_set = {c.conversation_id for c in selected}
        covered_action_threads = action_conv_ids.intersection(covered_threads_set)

        coverage_percent = len(covered_action_threads) / len(action_conv_ids) * 100

        print(
            f"✓ Covered {len(covered_action_threads)}/{len(action_conv_ids)} action threads ({coverage_percent:.1f}%)"
        )
        print(f"✓ Total threads covered: {metrics['covered_threads']}")
        print(f"✓ Discarded action-like chunks: {metrics['discarded_action_like']}")

        assert (
            coverage_percent >= 90
        ), f"Only {coverage_percent:.1f}% action thread coverage, expected ≥90%"

    def test_token_budget_protection(self):
        """Test that token budget is respected."""
        # Create many chunks that would exceed budget
        chunks = []
        for i in range(50):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-budget-{i}",
                conversation_id=f"conv-budget-{i}",
                token_count=200,  # Large chunks
                priority_score=5.0,
            )
            chunks.append(chunk)

        config_buckets = SelectionBucketsConfig(max_total_chunks=50)  # Would allow many
        config_weights = SelectionWeightsConfig()
        selector = ContextSelector(config_buckets, config_weights)

        selected = selector.select_context(chunks)
        metrics = selector.get_metrics()

        # Check that token budget is not exceeded
        total_tokens = sum(c.token_count for c in selected)

        print(f"✓ Selected {len(selected)} chunks")
        print(
            f"✓ Token budget used: {metrics['token_budget_used']}/{selector.context_budget_config.max_total_tokens}"
        )
        print(f"✓ Total tokens: {total_tokens}")

        assert (
            metrics["token_budget_used"] <= selector.context_budget_config.max_total_tokens
        ), f"Budget exceeded: {metrics['token_budget_used']}"
        assert (
            total_tokens <= selector.context_budget_config.max_total_tokens
        ), f"Total tokens {total_tokens} exceeds budget"

    def test_bucket_distribution(self):
        """Test that buckets are properly filled."""
        # Create diverse chunks for all buckets
        chunks = []

        # For threads_top bucket
        for i in range(15):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-thread-{i}",
                conversation_id=f"conv-thread-{i}",
                token_count=100,
                priority_score=5.0,
                message_metadata={
                    "from": "sender@example.com",
                    "to": ["user@example.com"],
                    "cc": [],
                    "subject": "Test",
                    "received_at": (
                        datetime.now(timezone.utc) - timedelta(minutes=i * 10)
                    ).isoformat(),
                    "importance": "Normal",
                    "is_flagged": False,
                    "has_attachments": False,
                    "attachment_types": [],
                },
            )
            chunks.append(chunk)

        # For addressed_to_me bucket (additional chunks from existing threads)
        for i in range(10):
            # Use existing thread IDs to create second chunks from same threads
            conv_id = f"conv-thread-{i % 5}"  # Reuse first 5 thread IDs
            chunk = self.create_test_chunk(
                evidence_id=f"ev-tome-{i}",
                conversation_id=conv_id,
                token_count=100,
                priority_score=6.0,
                addressed_to_me=True,
                message_metadata={
                    "from": "sender@example.com",
                    "to": ["user@example.com"],
                    "cc": [],
                    "subject": "Test - Addressed to Me",
                    "received_at": (
                        datetime.now(timezone.utc) - timedelta(minutes=i * 5)
                    ).isoformat(),
                    "importance": "Normal",
                    "is_flagged": False,
                    "has_attachments": False,
                    "attachment_types": [],
                },
            )
            chunks.append(chunk)

        # For dates_deadlines bucket
        for i in range(8):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-date-{i}",
                conversation_id=f"conv-date-{i}",
                token_count=100,
                priority_score=6.0,
                signals={
                    "action_verbs": [],
                    "dates": ["2024-12-31"],
                    "contains_question": False,
                    "sender_rank": 1,
                },
            )
            chunks.append(chunk)

        # For critical_senders bucket
        for i in range(6):
            chunk = self.create_test_chunk(
                evidence_id=f"ev-critical-{i}",
                conversation_id=f"conv-critical-{i}",
                token_count=100,
                priority_score=7.0,
                signals={
                    "action_verbs": [],
                    "dates": [],
                    "contains_question": False,
                    "sender_rank": 2,
                },
            )
            chunks.append(chunk)

        config_buckets = SelectionBucketsConfig(
            threads_top=10,
            addressed_to_me=8,
            dates_deadlines=6,
            critical_senders=4,
            max_total_chunks=30,
        )
        config_weights = SelectionWeightsConfig()
        selector = ContextSelector(config_buckets, config_weights)

        selected = selector.select_context(chunks)
        metrics = selector.get_metrics()

        print(f"✓ Bucket distribution: {metrics['selected_by_bucket']}")
        print(f"✓ Total selected: {sum(metrics['selected_by_bucket'].values())}")

        # Verify bucket targets are met or approached (allowing some flexibility due to token budget)
        assert metrics["selected_by_bucket"]["threads_top"] >= 8, "threads_top bucket under-filled"
        # Note: Some buckets may not fully fill due to token budget constraints and chunk competition
        assert (
            metrics["selected_by_bucket"].get("addressed_to_me", 0) >= 3
        ), f"addressed_to_me bucket under-filled: {metrics['selected_by_bucket'].get('addressed_to_me', 0)}"
        assert (
            metrics["selected_by_bucket"].get("dates_deadlines", 0) >= 3
        ), f"dates_deadlines bucket under-filled: got {metrics['selected_by_bucket'].get('dates_deadlines', 0)}"
        assert (
            metrics["selected_by_bucket"].get("critical_senders", 0) >= 3
        ), "critical_senders bucket under-filled"

        # Verify total doesn't exceed max
        assert sum(metrics["selected_by_bucket"].values()) >= len(selected)
        assert len(selected) <= config_buckets.max_total_chunks


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
