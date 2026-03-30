"""
Test EWS ingestion with mocked exchangelib.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from digest_core.ingest.ews import EWSIngest
from digest_core.config import Config


@pytest.fixture
def mock_config():
    """Mock configuration for EWS testing."""
    config = Mock(spec=Config)
    config.ews = Mock()
    config.ews.endpoint = "https://mail.company.com/EWS/Exchange.asmx"
    config.ews.user_upn = "test@company.com"
    config.ews.verify_ca = None
    config.ews.sync_state_path = "/tmp/test.state"
    config.ews.user_login = "testuser"
    config.ews.user_domain = "company.com"
    config.get_ews_password.return_value = "test_password"
    config.time = Mock()
    config.time.timezone = "UTC"
    config.time.window_type = "calendar_day"
    return config


@pytest.fixture
def ingester(mock_config):
    """EWS ingester with mocked configuration."""
    return EWSIngest(mock_config.ews)


def test_ntlm_authentication(ingester):
    """Test NTLM authentication setup."""
    with patch('digest_core.ingest.ews.NTLMAuth') as mock_ntlm:
        with patch('digest_core.ingest.ews.Account') as mock_account:
            mock_account.return_value = Mock()
            ingester._connect()
            mock_ntlm.assert_called_once()


def test_autodiscover_disabled(ingester):
    """Test that autodiscover is disabled."""
    with patch('digest_core.ingest.ews.Account') as mock_account:
        mock_account.return_value = Mock()
        ingester._connect()
        # Check that autodiscover=False is passed
        call_args = mock_account.call_args
        assert call_args[1]['autodiscover'] is False


def test_tls_context_setup(ingester):
    """Test TLS context setup with corporate CA."""
    with patch('digest_core.ingest.ews.ssl') as mock_ssl:
        with patch('digest_core.ingest.ews.BaseProtocol') as mock_protocol:
            ingester._setup_ssl_context()
            mock_ssl.create_default_context.assert_called_once()
            mock_protocol.SSL_CONTEXT = mock_ssl.create_default_context.return_value


def test_calendar_day_window(ingester):
    """Test calendar day window calculation."""
    test_date = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
    start_time, end_time = ingester._calculate_time_window(test_date, "calendar_day")
    
    expected_start = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    expected_end = datetime(2024, 1, 15, 23, 59, 59, 999999, tzinfo=timezone.utc)
    
    assert start_time == expected_start
    assert end_time == expected_end


def test_rolling_24h_window(ingester):
    """Test rolling 24h window calculation."""
    test_date = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
    start_time, end_time = ingester._calculate_time_window(test_date, "rolling_24h")
    
    expected_start = datetime(2024, 1, 14, 10, 30, tzinfo=timezone.utc)
    expected_end = test_date
    
    assert start_time == expected_start
    assert end_time == expected_end


def test_watermark_loading(ingester):
    """Test watermark loading from state file."""
    with patch('builtins.open', mock_open(read_data='2024-01-15T10:30:00Z')):
        with patch('digest_core.ingest.ews.Path.exists', return_value=True):
            watermark = ingester._load_watermark()
            assert watermark == datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)


def test_watermark_corrupted_fallback(ingester):
    """Test fallback to full interval when watermark is corrupted."""
    with patch('builtins.open', mock_open(read_data='invalid-timestamp')):
        with patch('digest_core.ingest.ews.Path.exists', return_value=True):
            watermark = ingester._load_watermark()
            assert watermark is None


def test_watermark_update(ingester):
    """Test watermark update to state file."""
    test_timestamp = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
    
    with patch('builtins.open', mock_open()) as mock_file:
        ingester._update_watermark(test_timestamp)
        mock_file.assert_called_once()
        # Check that ISO timestamp is written
        written_data = mock_file().write.call_args[0][0]
        assert "2024-01-15T10:30:00Z" in written_data


def test_message_normalization(ingester):
    """Test message normalization."""
    mock_message = Mock()
    mock_message.message_id = "test-message-id"
    mock_message.conversation_id = "test-conversation-id"
    mock_message.datetime_received = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
    mock_message.sender.email_address = "sender@company.com"
    mock_message.subject = "Test Subject"
    mock_message.text_body = "Test body content"
    
    normalized = ingester._normalize_message(mock_message)
    
    assert normalized.msg_id == "test-message-id"
    assert normalized.conversation_id == "test-conversation-id"
    assert normalized.datetime_received == datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
    assert normalized.sender.email_address == "sender@company.com"
    assert normalized.subject == "Test Subject"
    assert normalized.text_body == "Test body content"


def test_pagination_handling(ingester):
    """Test handling of multiple pages of messages."""
    # Mock first page with more_items_available=True
    mock_page1 = Mock()
    mock_page1.more_items_available = True
    mock_page1.__iter__ = Mock(return_value=iter([Mock(), Mock()]))
    
    # Mock second page with more_items_available=False
    mock_page2 = Mock()
    mock_page2.more_items_available = False
    mock_page2.__iter__ = Mock(return_value=iter([Mock()]))
    
    with patch.object(ingester, '_fetch_messages_with_retry') as mock_fetch:
        mock_fetch.side_effect = [mock_page1, mock_page2]
        
        messages = list(ingester._fetch_messages_paginated(Mock(), Mock(), Mock()))
        
        # Should have 3 messages total (2 from first page, 1 from second)
        assert len(messages) == 3
        assert mock_fetch.call_count == 2


def test_retry_logic(ingester):
    """Test retry logic for network errors."""
    with patch('digest_core.ingest.ews.tenacity.retry') as mock_retry:
        with patch.object(ingester, '_fetch_messages_with_retry') as mock_fetch:
            mock_fetch.side_effect = [
                Exception("Network error"),
                Exception("Network error"),
                Mock()  # Success on third attempt
            ]
            
            # This should not raise an exception due to retry logic
            try:
                ingester._fetch_messages_with_retry(Mock(), Mock(), Mock())
            except Exception:
                pass  # Expected to fail after retries
            
            assert mock_fetch.call_count == 3


def mock_open(read_data=''):
    """Helper to mock file operations."""
    from unittest.mock import mock_open as _mock_open
    return _mock_open(read_data=read_data)
