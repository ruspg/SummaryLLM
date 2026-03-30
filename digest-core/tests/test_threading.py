"""
Tests for enhanced threading system.

Covers:
- SubjectNormalizer: RE/FW/Ответ/[tags]/emoji removal
- ThreadMerge: semantic similarity fallback
- Anti-duplicator: checksum-based deduplication
- Redundancy index calculation
"""
import pytest
from datetime import datetime, timezone
from digest_core.threads.subject_normalizer import SubjectNormalizer, calculate_text_similarity
from digest_core.threads.build import ThreadBuilder, ConversationThread
from digest_core.ingest.ews import NormalizedMessage


# Test fixtures
@pytest.fixture
def normalizer():
    """SubjectNormalizer instance."""
    return SubjectNormalizer()


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    return [
        NormalizedMessage(
            msg_id="msg-001",
            conversation_id="conv-1",
            subject="Project Update",
            sender="alice@corp.com",
            sender_email="alice@corp.com",
            to_recipients=["bob@corp.com"],
            cc_recipients=[],
            datetime_received=base_time,
            text_body="Hello, here is the project update for Q1.",
        ),
        NormalizedMessage(
            msg_id="msg-002",
            conversation_id="conv-1",
            subject="RE: Project Update",
            sender="bob@corp.com",
            sender_email="bob@corp.com",
            to_recipients=["alice@corp.com"],
            cc_recipients=[],
            datetime_received=base_time,
            text_body="Thanks for the update. Looks good!",
        ),
    ]


class TestSubjectNormalizer:
    """Test SubjectNormalizer functionality."""
    
    def test_normalize_empty(self, normalizer):
        """Test empty subject."""
        norm, orig = normalizer.normalize("")
        assert norm == ""
        assert orig == ""
    
    def test_normalize_simple(self, normalizer):
        """Test simple subject without prefixes."""
        norm, orig = normalizer.normalize("Project Update")
        assert norm == "project update"
        assert orig == "Project Update"
    
    def test_normalize_re_prefix(self, normalizer):
        """Test RE: prefix removal."""
        norm, _ = normalizer.normalize("RE: Project Update")
        assert norm == "project update"
    
    def test_normalize_fwd_prefix(self, normalizer):
        """Test Fwd: prefix removal."""
        norm, _ = normalizer.normalize("Fwd: Important Document")
        assert norm == "important document"
    
    def test_normalize_russian_prefix_otvet(self, normalizer):
        """Test Russian 'Ответ:' prefix."""
        norm, _ = normalizer.normalize("Ответ: Проект обновление")
        assert norm == "проект обновление"
    
    def test_normalize_russian_prefix_peresl(self, normalizer):
        """Test Russian 'Пересл:' prefix."""
        norm, _ = normalizer.normalize("Пересл: Важный документ")
        assert norm == "важный документ"
    
    def test_normalize_nested_prefixes(self, normalizer):
        """Test nested RE: RE: Fwd: prefixes."""
        norm, _ = normalizer.normalize("RE: RE: Fwd: Status Update")
        assert norm == "status update"
    
    def test_normalize_external_marker(self, normalizer):
        """Test (External) marker removal."""
        norm, _ = normalizer.normalize("(External) Meeting Invitation")
        assert norm == "meeting invitation"
    
    def test_normalize_external_marker_brackets(self, normalizer):
        """Test [EXTERNAL] marker removal."""
        norm, _ = normalizer.normalize("[EXTERNAL] Security Alert")
        assert norm == "security alert"
    
    def test_normalize_jira_tag(self, normalizer):
        """Test [JIRA-123] tag removal."""
        norm, _ = normalizer.normalize("[JIRA-123] Bug fix required")
        assert norm == "bug fix required"
    
    def test_normalize_multiple_tags(self, normalizer):
        """Test multiple [tags] removal."""
        norm, _ = normalizer.normalize("[URGENT] [PROJ-456] Critical issue")
        assert norm == "critical issue"
    
    def test_normalize_emoji(self, normalizer):
        """Test emoji removal."""
        norm, _ = normalizer.normalize("📧 Email reminder 🔔")
        assert norm == "email reminder"
    
    def test_normalize_smart_quotes(self, normalizer):
        """Test smart quotes → straight quotes."""
        norm, _ = normalizer.normalize('"Project" status update')
        assert norm == '"project" status update'
    
    def test_normalize_em_dash(self, normalizer):
        """Test em dash → hyphen."""
        norm, _ = normalizer.normalize("Q1 Results — Final")
        assert norm == "q1 results - final"
    
    def test_normalize_complex_case(self, normalizer):
        """Test complex case with multiple transformations."""
        subject = 'RE: Fwd: [EXTERNAL] [JIRA-789] 🚨 Important — "Status Update"'
        norm, orig = normalizer.normalize(subject)
        assert norm == 'important - "status update"'
        assert orig == subject
    
    def test_is_similar_true(self, normalizer):
        """Test subjects that should be similar."""
        assert normalizer.is_similar(
            "Project Update",
            "RE: Project Update"
        )
    
    def test_is_similar_false(self, normalizer):
        """Test subjects that should not be similar."""
        assert not normalizer.is_similar(
            "Project Update",
            "Meeting Invitation"
        )


class TestTextSimilarity:
    """Test text similarity calculation."""
    
    def test_identical_texts(self):
        """Test identical texts."""
        text = "This is a test message for similarity."
        similarity = calculate_text_similarity(text, text)
        assert similarity == 1.0
    
    def test_similar_texts(self):
        """Test similar texts."""
        text1 = "This is a test message for the project update."
        text2 = "This is a test message for the project status."
        similarity = calculate_text_similarity(text1, text2)
        assert similarity > 0.7  # Should be quite similar
    
    def test_different_texts(self):
        """Test different texts."""
        text1 = "Project update for Q1 deliverables."
        text2 = "Meeting invitation for tomorrow at 3pm."
        similarity = calculate_text_similarity(text1, text2)
        assert similarity < 0.3  # Should be quite different
    
    def test_empty_texts(self):
        """Test empty texts."""
        similarity = calculate_text_similarity("", "test")
        assert similarity == 0.0


class TestThreadBuilder:
    """Test ThreadBuilder functionality."""
    
    def test_build_single_thread(self, sample_messages):
        """Test building a single thread from related messages."""
        builder = ThreadBuilder()
        threads = builder.build_threads(sample_messages)
        
        assert len(threads) == 1
        assert threads[0].message_count == 2
        assert threads[0].conversation_id == "conv_conv-1"
    
    def test_build_multiple_threads_different_conversations(self):
        """Test building multiple threads from different conversations."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        messages = [
            NormalizedMessage(
                msg_id="msg-001",
                conversation_id="conv-1",
                subject="Project A",
                sender="alice@corp.com",
                sender_email="alice@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Project A update",
            ),
            NormalizedMessage(
                msg_id="msg-002",
                conversation_id="conv-2",
                subject="Project B",
                sender="bob@corp.com",
                sender_email="bob@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Project B update",
            ),
        ]
        
        builder = ThreadBuilder()
        threads = builder.build_threads(messages)
        
        assert len(threads) == 2
    
    def test_merge_by_normalized_subject(self):
        """Test merging threads by normalized subject."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        messages = [
            NormalizedMessage(
                msg_id="msg-001",
                conversation_id=None,  # No conv_id, will use subject
                subject="Status Update",
                sender="alice@corp.com",
                sender_email="alice@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="First update",
            ),
            NormalizedMessage(
                msg_id="msg-002",
                conversation_id=None,
                subject="RE: Status Update",  # Should normalize to same
                sender="bob@corp.com",
                sender_email="bob@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Second update",
            ),
        ]
        
        builder = ThreadBuilder()
        threads = builder.build_threads(messages)
        
        # Should merge into one thread
        assert len(threads) == 1
        assert threads[0].message_count == 2
        
        # Check stats
        stats = builder.get_stats()
        assert stats['threads_merged_by_subject'] > 0
    
    def test_merge_by_semantic_similarity(self):
        """Test merging threads by semantic similarity."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        # Very similar messages, same subject
        messages = [
            NormalizedMessage(
                msg_id="msg-001",
                conversation_id=None,
                subject="Project Update",
                sender="alice@corp.com",
                sender_email="alice@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="The Q1 project deliverables are on track and progressing well.",
            ),
            NormalizedMessage(
                msg_id="msg-002",
                conversation_id=None,
                subject="Project Update",  # Same subject
                sender="bob@corp.com",
                sender_email="bob@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="The Q1 project deliverables are on track and looking good.",  # Similar content
            ),
        ]
        
        builder = ThreadBuilder(semantic_similarity_threshold=0.7)
        threads = builder.build_threads(messages)
        
        # Should merge into one thread by semantic similarity
        assert len(threads) == 1
        assert threads[0].message_count == 2


class TestDeduplication:
    """Test anti-duplicator functionality."""
    
    def test_exact_duplicate_removal(self):
        """Test removal of exact duplicate messages."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        # Two messages with identical body
        messages = [
            NormalizedMessage(
                msg_id="msg-001",
                conversation_id="conv-1",
                subject="Update",
                sender="alice@corp.com",
                sender_email="alice@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Exact same content here.",
            ),
            NormalizedMessage(
                msg_id="msg-002",  # Different ID
                conversation_id="conv-1",
                subject="Update",
                sender="alice@corp.com",
                sender_email="alice@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Exact same content here.",  # Identical body
            ),
        ]
        
        builder = ThreadBuilder()
        threads = builder.build_threads(messages)
        
        # Should deduplicate
        thread = threads[0]
        assert thread.message_count == 1  # Only one message kept
        
        # Check stats
        stats = builder.get_stats()
        assert stats['duplicates_found'] == 1


class TestRedundancyIndex:
    """Test redundancy index calculation."""
    
    def test_no_redundancy(self):
        """Test redundancy index with no duplicates."""
        builder = ThreadBuilder()
        redundancy = builder.calculate_redundancy_index(10, 10)
        assert redundancy == 0.0
    
    def test_some_redundancy(self):
        """Test redundancy index with some duplicates."""
        builder = ThreadBuilder()
        redundancy = builder.calculate_redundancy_index(10, 7)
        assert redundancy == 0.3  # 30% reduction
    
    def test_high_redundancy(self):
        """Test redundancy index with high duplication."""
        builder = ThreadBuilder()
        redundancy = builder.calculate_redundancy_index(10, 5)
        assert redundancy == 0.5  # 50% reduction
    
    def test_redundancy_target(self):
        """Test that redundancy meets ≥30% reduction goal."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        # Create dataset with expected redundancy
        messages = []
        
        # Original messages
        for i in range(10):
            messages.append(
                NormalizedMessage(
                    msg_id=f"msg-{i}",
                    conversation_id=None,
                    subject=f"Subject {i % 3}",  # Only 3 unique subjects
                    sender="alice@corp.com",
                    sender_email="alice@corp.com",
                    to_recipients=[],
                    cc_recipients=[],
                    datetime_received=base_time,
                    text_body=f"Content for message {i % 5}",  # Some duplicate content
                )
            )
        
        # Add some exact duplicates
        messages.extend([
            NormalizedMessage(
                msg_id=f"msg-dup-{i}",
                conversation_id=None,
                subject=f"Subject {i % 3}",
                sender="alice@corp.com",
                sender_email="alice@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body=f"Content for message {i % 5}",  # Duplicate body
            )
            for i in range(5)
        ])
        
        builder = ThreadBuilder()
        threads = builder.build_threads(messages)
        
        original_count = len(messages)
        unique_count = sum(len(t.messages) for t in threads)
        redundancy = builder.calculate_redundancy_index(original_count, unique_count)
        
        # DoD: redundancy_index ↓ ≥30%
        assert redundancy >= 0.30, f"Redundancy {redundancy*100:.1f}% below target 30%"


class TestThreadingStatistics:
    """Test threading statistics tracking."""
    
    def test_stats_tracking(self):
        """Test that statistics are properly tracked."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        messages = [
            NormalizedMessage(
                msg_id="msg-001",
                conversation_id="conv-1",
                subject="Original",
                sender="alice@corp.com",
                sender_email="alice@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Original content",
            ),
            NormalizedMessage(
                msg_id="msg-002",
                conversation_id="conv-1",
                subject="RE: Original",
                sender="bob@corp.com",
                sender_email="bob@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Reply content",
            ),
        ]
        
        builder = ThreadBuilder()
        threads = builder.build_threads(messages)
        
        stats = builder.get_stats()
        
        # Check that stats are populated
        assert 'threads_merged_by_id' in stats
        assert 'threads_merged_by_subject' in stats
        assert 'threads_merged_by_semantic' in stats
        assert 'subjects_normalized' in stats
        assert 'duplicates_found' in stats
        
        # Should have merged by conversation_id
        assert stats['threads_merged_by_id'] > 0


class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_messages(self):
        """Test with empty message list."""
        builder = ThreadBuilder()
        threads = builder.build_threads([])
        assert len(threads) == 0
    
    def test_single_message(self):
        """Test with single message."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        messages = [
            NormalizedMessage(
                msg_id="msg-001",
                conversation_id=None,
                subject="Single",
                sender="alice@corp.com",
                sender_email="alice@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Single message",
            )
        ]
        
        builder = ThreadBuilder()
        threads = builder.build_threads(messages)
        
        assert len(threads) == 1
        assert threads[0].message_count == 1
    
    def test_messages_without_subject(self):
        """Test messages without subject."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        messages = [
            NormalizedMessage(
                msg_id="msg-001",
                conversation_id=None,
                subject="",  # Empty subject
                sender="alice@corp.com",
                sender_email="alice@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Content 1",
            ),
            NormalizedMessage(
                msg_id="msg-002",
                conversation_id=None,
                subject="",  # Empty subject
                sender="bob@corp.com",
                sender_email="bob@corp.com",
                to_recipients=[],
                cc_recipients=[],
                datetime_received=base_time,
                text_body="Content 2",
            ),
        ]
        
        builder = ThreadBuilder()
        threads = builder.build_threads(messages)
        
        # Should create separate threads
        assert len(threads) == 2
