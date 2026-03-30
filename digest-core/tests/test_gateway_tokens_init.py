"""
Tests for token counter initialization in LLM gateway.
Ensures no UnboundLocalError when usage data is missing.
"""

import pytest
from unittest.mock import Mock
import httpx


def test_tokens_initialized_before_try(monkeypatch):
    """Test that tokens_in/out are initialized before try block."""
    from digest_core.llm.gateway import LLMGateway
    from digest_core.config import LLMConfig

    # Mock environment variable
    monkeypatch.setenv("LLM_TOKEN", "test-token")

    # Create config
    config = LLMConfig(
        endpoint="https://test.api.com/v1/chat/completions",
        token="test-token",
        model="test-model",
    )

    # Create gateway
    gateway = LLMGateway(config=config)

    # Mock client to return response without usage data
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"sections": []}'}}]
        # Note: NO "usage" field
    }
    mock_response.headers = {}  # No usage headers either
    mock_response.raise_for_status = Mock()

    gateway.client.post = Mock(return_value=mock_response)

    # Should not raise UnboundLocalError
    try:
        result = gateway._make_request_with_retry(
            messages=[{"role": "user", "content": "test"}],
            trace_id="test-trace",
            digest_date="2025-01-01",
        )

        # Should have meta with default values
        assert "meta" in result
        assert result["meta"]["tokens_in"] == 0
        assert result["meta"]["tokens_out"] == 0

    except UnboundLocalError as e:
        pytest.fail(f"UnboundLocalError raised: {e}")


def test_tokens_from_usage_field(monkeypatch):
    """Test that tokens are extracted from usage field when available."""
    from digest_core.llm.gateway import LLMGateway
    from digest_core.config import LLMConfig

    # Mock environment variable
    monkeypatch.setenv("LLM_TOKEN", "test-token")

    config = LLMConfig(
        endpoint="https://test.api.com/v1/chat/completions",
        token="test-token",
        model="test-model",
    )

    gateway = LLMGateway(config=config)

    # Mock response WITH usage data
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"sections": []}'}}],
        "usage": {"prompt_tokens": 150, "completion_tokens": 50},
    }
    mock_response.headers = {}
    mock_response.raise_for_status = Mock()

    gateway.client.post = Mock(return_value=mock_response)

    result = gateway._make_request_with_retry(
        messages=[{"role": "user", "content": "test"}],
        trace_id="test-trace",
        digest_date="2025-01-01",
    )

    # Should extract tokens from usage
    assert result["meta"]["tokens_in"] == 150
    assert result["meta"]["tokens_out"] == 50


def test_tokens_from_headers(monkeypatch):
    """Test that tokens are extracted from headers when available."""
    from digest_core.llm.gateway import LLMGateway
    from digest_core.config import LLMConfig

    # Mock environment variable
    monkeypatch.setenv("LLM_TOKEN", "test-token")

    config = LLMConfig(
        endpoint="https://test.api.com/v1/chat/completions",
        token="test-token",
        model="test-model",
    )

    gateway = LLMGateway(config=config)

    # Mock response with usage in headers
    mock_response = Mock()
    mock_response.json.return_value = {"choices": [{"message": {"content": '{"sections": []}'}}]}
    mock_response.headers = {"x-llm-tokens-in": "200", "x-llm-tokens-out": "75"}
    mock_response.raise_for_status = Mock()

    gateway.client.post = Mock(return_value=mock_response)

    result = gateway._make_request_with_retry(
        messages=[{"role": "user", "content": "test"}],
        trace_id="test-trace",
        digest_date="2025-01-01",
    )

    # Should extract tokens from headers
    assert result["meta"]["tokens_in"] == 200
    assert result["meta"]["tokens_out"] == 75


def test_no_unbound_error_on_http_error(monkeypatch):
    """Test that no UnboundLocalError occurs even when HTTP request fails."""
    from digest_core.llm.gateway import LLMGateway
    from digest_core.config import LLMConfig

    # Mock environment variable
    monkeypatch.setenv("LLM_TOKEN", "test-token")

    config = LLMConfig(
        endpoint="https://test.api.com/v1/chat/completions",
        token="test-token",
        model="test-model",
    )

    gateway = LLMGateway(config=config)

    # Mock client to raise HTTP error
    def raise_http_error(*args, **kwargs):
        response = Mock()
        response.status_code = 500
        raise httpx.HTTPStatusError("Server error", request=Mock(), response=response)

    gateway.client.post = Mock(side_effect=raise_http_error)

    # Should raise HTTPStatusError, but NOT UnboundLocalError
    with pytest.raises(httpx.HTTPStatusError):
        gateway._make_request_with_retry(
            messages=[{"role": "user", "content": "test"}],
            trace_id="test-trace",
            digest_date="2025-01-01",
        )
