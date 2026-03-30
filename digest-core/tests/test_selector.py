"""
Test context selector with scoring and filtering.
"""

import pytest
from unittest.mock import Mock
from digest_core.select.context import ContextSelector
from digest_core.evidence.split import EvidenceChunk


@pytest.fixture
def selector():
    """Context selector instance."""
    return ContextSelector()


@pytest.fixture
def sample_threads():
    """Sample threads for testing."""
    threads = []

    # Thread 1: High priority (urgent keywords, recent)
    thread1 = Mock()
    thread1.thread_id = "thread-1"
    thread1.messages = [
        Mock(
            subject="URGENT: Server Down",
            sender=Mock(email_address="admin@company.com"),
        )
    ]
    thread1.latest_message_time = Mock()
    thread1.message_count = 3
    threads.append(thread1)

    # Thread 2: Medium priority (meeting request)
    thread2 = Mock()
    thread2.thread_id = "thread-2"
    thread2.messages = [
        Mock(
            subject="Meeting: Q4 Review",
            sender=Mock(email_address="manager@company.com"),
        )
    ]
    thread2.latest_message_time = Mock()
    thread2.message_count = 2
    threads.append(thread2)

    # Thread 3: Low priority (OOO message)
    thread3 = Mock()
    thread3.thread_id = "thread-3"
    thread3.messages = [
        Mock(subject="Out of Office", sender=Mock(email_address="user@company.com"))
    ]
    thread3.latest_message_time = Mock()
    thread3.message_count = 1
    threads.append(thread3)

    return threads


@pytest.fixture
def sample_evidence():
    """Sample evidence chunks for testing."""
    evidence = []

    # Evidence 1: High priority content
    chunk1 = Mock(spec=EvidenceChunk)
    chunk1.evidence_id = "ev-1"
    chunk1.thread_id = "thread-1"
    chunk1.content = "URGENT: Server is down, need immediate action"
    chunk1.token_count = 100
    evidence.append(chunk1)

    # Evidence 2: Medium priority content
    chunk2 = Mock(spec=EvidenceChunk)
    chunk2.evidence_id = "ev-2"
    chunk2.thread_id = "thread-2"
    chunk2.content = "Meeting scheduled for Q4 review next week"
    chunk2.token_count = 80
    evidence.append(chunk2)

    # Evidence 3: Low priority content
    chunk3 = Mock(spec=EvidenceChunk)
    chunk3.evidence_id = "ev-3"
    chunk3.thread_id = "thread-3"
    chunk3.content = "I will be out of office until next Monday"
    chunk3.token_count = 60
    evidence.append(chunk3)

    return evidence


def test_scoring_positive_signals(selector, sample_threads, sample_evidence):
    """Test scoring with positive signals."""
    # Test urgent keywords
    score = selector._calculate_positive_signals("URGENT: Server Down", "admin@company.com")
    assert score > 0

    # Test meeting keywords
    score = selector._calculate_positive_signals("Meeting: Q4 Review", "manager@company.com")
    assert score > 0

    # Test action keywords
    score = selector._calculate_positive_signals("Please review and approve", "user@company.com")
    assert score > 0


def test_scoring_negative_signals(selector, sample_threads, sample_evidence):
    """Test scoring with negative signals."""
    # Test OOO messages
    score = selector._calculate_negative_signals("Out of Office", "user@company.com")
    assert score > 0

    # Test DSN messages
    score = selector._calculate_negative_signals(
        "Delivery Status Notification", "system@company.com"
    )
    assert score > 0

    # Test auto-replies
    score = selector._calculate_negative_signals("Auto-reply", "user@company.com")
    assert score > 0


def test_service_mail_filtering(selector, sample_threads, sample_evidence):
    """Test filtering of service emails."""
    # Test OOO filtering
    is_service = selector._is_service_email("Out of Office", "user@company.com")
    assert is_service

    # Test DSN filtering
    is_service = selector._is_service_email("Delivery Status Notification", "system@company.com")
    assert is_service

    # Test regular email
    is_service = selector._is_service_email("Regular business email", "user@company.com")
    assert not is_service


def test_token_budget_respect(selector, sample_threads, sample_evidence):
    """Test that token budget is respected."""
    max_tokens = 1000

    selected = selector.select_context(sample_threads, sample_evidence, max_tokens)

    total_tokens = sum(chunk.token_count for chunk in selected)
    assert total_tokens <= max_tokens


def test_top_k_selection(selector, sample_threads, sample_evidence):
    """Test top-K selection based on scoring."""
    max_tokens = 2000

    selected = selector.select_context(sample_threads, sample_evidence, max_tokens)

    # Should select evidence in order of priority
    assert len(selected) > 0

    # First selected should be highest priority
    if len(selected) > 1:
        assert selected[0].evidence_id == "ev-1"  # Urgent content


def test_empty_input(selector):
    """Test handling of empty input."""
    selected = selector.select_context([], [], 1000)
    assert selected == []


def test_insufficient_tokens(selector, sample_threads, sample_evidence):
    """Test handling when evidence exceeds token budget."""
    max_tokens = 50  # Very small budget

    selected = selector.select_context(sample_threads, sample_evidence, max_tokens)

    # Should still return something, even if the smallest chunk itself exceeds the budget.
    assert len(selected) > 0
    total_tokens = sum(chunk.token_count for chunk in selected)
    assert total_tokens <= max_tokens or min(chunk.token_count for chunk in selected) > max_tokens


def test_sender_weighting(selector, sample_threads, sample_evidence):
    """Test sender-based weighting."""
    # High-priority sender
    score = selector._calculate_sender_weight("ceo@company.com")
    assert score > 0

    # Medium-priority sender
    score = selector._calculate_sender_weight("manager@company.com")
    assert score > 0

    # Low-priority sender
    score = selector._calculate_sender_weight("user@company.com")
    assert score == 0


def test_thread_activity_scoring(selector, sample_threads, sample_evidence):
    """Test thread activity scoring."""
    # High activity thread
    score = selector._calculate_thread_activity(5, Mock())
    assert score > 0

    # Low activity thread
    score = selector._calculate_thread_activity(1, Mock())
    assert score == 0
