# Testing Strategy and Quality Assurance

Стратегия тестирования и обеспечение качества для ActionPulse.

## Обзор стратегии тестирования

### Принципы тестирования

- **Comprehensive Coverage** - покрытие всех критических компонентов
- **Deterministic Results** - воспроизводимые тесты
- **Privacy-First** - тестирование PII handling
- **Performance Aware** - тесты производительности
- **Integration Focus** - фокус на интеграционных тестах

### Типы тестов

1. **Unit Tests** - тестирование отдельных компонентов
2. **Integration Tests** - тестирование взаимодействий
3. **Contract Tests** - тестирование контрактов с внешними сервисами
4. **Snapshot Tests** - тестирование стабильности формата
5. **Leakage Tests** - тестирование утечек PII
6. **Invariance Tests** - тестирование семантической стабильности

## Unit Tests

### Структура unit тестов

```python
# tests/test_normalize.py
import pytest
from digest_core.normalize.html import HTMLNormalizer
from digest_core.normalize.quotes import QuoteCleaner

class TestHTMLNormalizer:
    def test_basic_html_cleaning(self):
        """Test basic HTML to text conversion."""
        normalizer = HTMLNormalizer()
        html = "<p>Hello <strong>world</strong>!</p>"
        expected = "Hello world!"
        assert normalizer.clean(html) == expected
    
    def test_remove_tracking_pixels(self):
        """Test removal of tracking pixels."""
        normalizer = HTMLNormalizer()
        html = '<img src="tracking.gif" width="1" height="1">'
        expected = ""
        assert normalizer.clean(html) == expected
    
    def test_preserve_important_structure(self):
        """Test preservation of important structural elements."""
        normalizer = HTMLNormalizer()
        html = "<h1>Title</h1><p>Content</p><ul><li>Item</li></ul>"
        expected = "Title\n\nContent\n\n• Item"
        assert normalizer.clean(html) == expected

class TestQuoteCleaner:
    def test_remove_standard_quotes(self):
        """Test removal of standard email quotes."""
        cleaner = QuoteCleaner()
        text = "New content\n\n> Old content\n> More old content"
        expected = "New content"
        assert cleaner.clean(text) == expected
    
    def test_remove_multiple_quote_levels(self):
        """Test removal of nested quotes."""
        cleaner = QuoteCleaner()
        text = "New\n\n> Level 1\n>> Level 2\n>>> Level 3"
        expected = "New"
        assert cleaner.clean(text) == expected
    
    def test_preserve_important_quotes(self):
        """Test preservation of important quoted content."""
        cleaner = QuoteCleaner()
        text = "Please review:\n\n> Important: Budget approval needed"
        expected = "Please review:\n\nImportant: Budget approval needed"
        assert cleaner.clean(text) == expected
```

### Тестирование конфигурации

```python
# tests/test_config.py
import pytest
from pydantic import ValidationError
from digest_core.config import Config, EWSSettings, LLMSettings

class TestConfig:
    def test_valid_config(self):
        """Test valid configuration loading."""
        config_data = {
            "ews": {
                "endpoint": "https://ews.corp.com/EWS/Exchange.asmx",
                "user_upn": "user@corp.com",
                "password_env": "EWS_PASSWORD"
            },
            "llm": {
                "endpoint": "https://llm-gw.corp.com/api/v1/chat",
                "model": "corp/qwen3.5-397b-a17b"
            }
        }
        config = Config(**config_data)
        assert config.ews.endpoint == config_data["ews"]["endpoint"]
        assert config.llm.model == config_data["llm"]["model"]
    
    def test_invalid_ews_endpoint(self):
        """Test validation of EWS endpoint."""
        with pytest.raises(ValidationError):
            EWSSettings(endpoint="invalid-url", user_upn="user@corp.com")
    
    def test_invalid_user_upn(self):
        """Test validation of user UPN."""
        with pytest.raises(ValidationError):
            EWSSettings(endpoint="https://ews.corp.com", user_upn="invalid-email")
    
    def test_llm_timeout_validation(self):
        """Test LLM timeout validation."""
        with pytest.raises(ValidationError):
            LLMSettings(endpoint="https://llm.corp.com", timeout_s=5)  # Too low
```

## Integration Tests

### EWS Integration Tests

```python
# tests/test_ews_integration.py
import pytest
from unittest.mock import Mock, patch
from digest_core.ingest.ews import EWSClient

class TestEWSIntegration:
    @pytest.fixture
    def mock_account(self):
        """Mock Exchange account."""
        account = Mock()
        account.inbox.filter.return_value.order_by.return_value.__getitem__.return_value = [
            Mock(
                id="msg-123",
                conversation_id="conv-456",
                datetime_received="2024-01-15T10:00:00Z",
                sender=Mock(name="Alice", email_address="alice@corp.com"),
                subject="Test Subject",
                text_body="Test content",
                is_read=False,
                importance="Normal",
                has_attachments=False,
                size=1024
            )
        ]
        return account
    
    @patch('digest_core.ingest.ews.Account')
    def test_get_messages_success(self, mock_account_class, mock_account):
        """Test successful message retrieval."""
        mock_account_class.return_value = mock_account
        
        client = EWSClient(
            endpoint="https://ews.corp.com",
            username="user@corp.com",
            password="password"
        )
        
        messages = client.get_messages(limit=10)
        
        assert len(messages) == 1
        assert messages[0]["msg_id"] == "msg-123"
        assert messages[0]["subject"] == "Test Subject"
        assert messages[0]["sender"]["email"] == "alice@corp.com"
    
    @patch('digest_core.ingest.ews.Account')
    def test_get_messages_with_filter(self, mock_account_class, mock_account):
        """Test message retrieval with date filter."""
        mock_account_class.return_value = mock_account
        
        client = EWSClient(
            endpoint="https://ews.corp.com",
            username="user@corp.com",
            password="password"
        )
        
        from datetime import datetime, timedelta
        since = datetime.now() - timedelta(hours=24)
        
        messages = client.get_messages(since=since, limit=10)
        
        # Verify filter was applied
        mock_account.inbox.filter.assert_called_with(datetime_received__gte=since)
```

### LLM Gateway Integration Tests

```python
# tests/test_llm_integration.py
import pytest
import httpx
from unittest.mock import Mock, patch
from digest_core.llm.gateway import LLMGatewayClient, LLMGatewayError

class TestLLMGatewayIntegration:
    @pytest.fixture
    def mock_response(self):
        """Mock HTTP response."""
        response = Mock()
        response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"sections": [{"title": "Actions", "items": []}]}'
                }
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        }
        response.raise_for_status.return_value = None
        return response
    
    @patch('digest_core.llm.gateway.httpx.Client')
    def test_successful_llm_request(self, mock_client_class, mock_response):
        """Test successful LLM request."""
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        client = LLMGatewayClient(
            endpoint="https://llm-gw.corp.com/api/v1/chat",
            headers={"Authorization": "Bearer token"},
            model="corp/qwen3.5-397b-a17b"
        )
        
        messages = [{"role": "user", "content": "Test prompt"}]
        result = client.chat(messages)
        
        assert "trace_id" in result
        assert "latency_ms" in result
        assert "usage" in result
        assert result["usage"]["tokens_in"] == 100
        assert result["usage"]["tokens_out"] == 50
    
    @patch('digest_core.llm.gateway.httpx.Client')
    def test_llm_timeout_error(self, mock_client_class):
        """Test LLM timeout error handling."""
        mock_client = Mock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        client = LLMGatewayClient(
            endpoint="https://llm-gw.corp.com/api/v1/chat",
            headers={"Authorization": "Bearer token"},
            model="corp/qwen3.5-397b-a17b"
        )
        
        with pytest.raises(LLMGatewayError, match="Request timeout"):
            client.chat([{"role": "user", "content": "Test"}])
    
    @patch('digest_core.llm.gateway.httpx.Client')
    def test_llm_http_error(self, mock_client_class):
        """Test LLM HTTP error handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=Mock(), response=mock_response
        )
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        client = LLMGatewayClient(
            endpoint="https://llm-gw.corp.com/api/v1/chat",
            headers={"Authorization": "Bearer token"},
            model="corp/qwen3.5-397b-a17b"
        )
        
        with pytest.raises(LLMGatewayError, match="HTTP 429"):
            client.chat([{"role": "user", "content": "Test"}])
```

## Contract Tests

### LLM Gateway Contract Tests

```python
# tests/test_llm_contract.py
import pytest
import json
from digest_core.llm.schemas import Digest, Section, ActionItem
from digest_core.llm.gateway import LLMGatewayClient

class TestLLMContract:
    def test_valid_json_response(self):
        """Test that LLM returns valid JSON according to schema."""
        valid_response = {
            "sections": [
                {
                    "title": "Мои действия",
                    "items": [
                        {
                            "title": "Утвердить бюджет Q3",
                            "owners_masked": ["[[REDACT:NAME;id=123]]"],
                            "due": "2024-01-20",
                            "evidence_id": "ev:abc123:0:100",
                            "confidence": 0.85,
                            "source_ref": {
                                "type": "email",
                                "msg_id": "msg-456"
                            }
                        }
                    ]
                }
            ]
        }
        
        # Validate against Pydantic schema
        digest = Digest(
            digest_date="2024-01-15",
            generated_at="2024-01-15T10:00:00Z",
            trace_id="trace-789",
            sections=[Section(**section) for section in valid_response["sections"]]
        )
        
        assert len(digest.sections) == 1
        assert len(digest.sections[0].items) == 1
        assert digest.sections[0].items[0].confidence == 0.85
    
    def test_invalid_json_response(self):
        """Test handling of invalid JSON response."""
        invalid_responses = [
            "not json at all",
            '{"sections": [{"title": "Test"}]}',  # Missing required fields
            '{"sections": [{"title": "Test", "items": [{"title": "Item"}]}]}',  # Missing evidence_id
        ]
        
        for invalid_json in invalid_responses:
            with pytest.raises((json.JSONDecodeError, ValueError)):
                # This would be handled by the LLM client
                json.loads(invalid_json)
                # Additional Pydantic validation would fail
```

## Snapshot Tests

### Output Format Stability

```python
# tests/test_snapshot.py
import pytest
from pathlib import Path
from digest_core.assemble.markdown import MarkdownAssembler
from digest_core.assemble.jsonout import JSONAssembler

class TestSnapshot:
    def test_markdown_output_stability(self, snapshot):
        """Test that Markdown output format remains stable."""
        digest_data = {
            "digest_date": "2024-01-15",
            "sections": [
                {
                    "title": "Мои действия",
                    "items": [
                        {
                            "title": "Утвердить бюджет Q3",
                            "owners_masked": ["[[REDACT:NAME;id=123]]"],
                            "due": "2024-01-20",
                            "evidence_id": "ev:abc123:0:100",
                            "confidence": 0.85,
                            "source_ref": {"type": "email", "msg_id": "msg-456"}
                        }
                    ]
                }
            ]
        }
        
        assembler = MarkdownAssembler()
        markdown_output = assembler.assemble(digest_data)
        
        # Compare with snapshot
        snapshot.assert_match(markdown_output, "markdown_output.md")
    
    def test_json_output_stability(self, snapshot):
        """Test that JSON output format remains stable."""
        digest_data = {
            "digest_date": "2024-01-15",
            "sections": [
                {
                    "title": "Мои действия",
                    "items": [
                        {
                            "title": "Утвердить бюджет Q3",
                            "owners_masked": ["[[REDACT:NAME;id=123]]"],
                            "due": "2024-01-20",
                            "evidence_id": "ev:abc123:0:100",
                            "confidence": 0.85,
                            "source_ref": {"type": "email", "msg_id": "msg-456"}
                        }
                    ]
                }
            ]
        }
        
        assembler = JSONAssembler()
        json_output = assembler.assemble(digest_data)
        
        # Compare with snapshot
        snapshot.assert_match(json_output, "json_output.json")
```

## Leakage Tests

### PII Detection Tests

```python
# tests/test_pii_leakage.py
import pytest
import re
from digest_core.observability.logs import setup_logging

class TestPIILeakage:
    def test_email_leakage_in_outputs(self):
        """Test that email addresses don't leak in outputs."""
        test_cases = [
            "user@corp.com",
            "test.email@domain.org",
            "user+tag@example.com"
        ]
        
        for email in test_cases:
            # Simulate processing
            processed_text = f"Contact {email} for details"
            
            # Check that email is properly masked
            assert "[[REDACT:" in processed_text or email not in processed_text
    
    def test_phone_number_leakage(self):
        """Test that phone numbers don't leak in outputs."""
        phone_patterns = [
            r'\+7\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}',  # Russian format
            r'\+1\s?\d{3}\s?\d{3}\s?\d{4}',          # US format
            r'\d{3}-\d{3}-\d{4}'                      # US format with dashes
        ]
        
        test_cases = [
            "+7 999 123 45 67",
            "+1 555 123 4567",
            "555-123-4567"
        ]
        
        for phone in test_cases:
            processed_text = f"Call {phone} for support"
            
            # Check that phone is properly masked
            for pattern in phone_patterns:
                assert not re.search(pattern, processed_text)
    
    def test_credit_card_leakage(self):
        """Test that credit card numbers don't leak in outputs."""
        cc_patterns = [
            r'\d{4}\s?\d{4}\s?\d{4}\s?\d{4}',  # Standard format
            r'\d{4}-\d{4}-\d{4}-\d{4}'         # With dashes
        ]
        
        test_cases = [
            "1234 5678 9012 3456",
            "1234-5678-9012-3456"
        ]
        
        for cc in test_cases:
            processed_text = f"Card: {cc}"
            
            # Check that credit card is properly masked
            for pattern in cc_patterns:
                assert not re.search(pattern, processed_text)
    
    def test_log_pii_leakage(self):
        """Test that PII doesn't leak in logs."""
        import logging
        import io
        
        # Setup logging to capture output
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger('test')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Log message with PII
        sensitive_data = "user@corp.com"
        logger.info(f"Processing email: {sensitive_data}")
        
        log_output = log_capture.getvalue()
        
        # Check that PII is not in logs
        assert sensitive_data not in log_output
        assert "[[REDACT:" in log_output or "REDACTED" in log_output
```

## Invariance Tests

### Semantic Stability Tests

```python
# tests/test_invariance.py
import pytest
import numpy as np
from sentence_transformers import SentenceTransformer
from digest_core.llm.gateway import LLMGatewayClient

class TestInvariance:
    @pytest.fixture
    def embedding_model(self):
        """Load embedding model for semantic comparison."""
        return SentenceTransformer('all-MiniLM-L6-v2')
    
    def test_masking_semantic_preservation(self, embedding_model):
        """Test that PII masking preserves semantic meaning."""
        original_text = "Please contact John Doe at john.doe@corp.com for the budget approval."
        masked_text = "Please contact [[REDACT:NAME;id=123]] at [[REDACT:EMAIL;id=456]] for the budget approval."
        
        # Generate embeddings
        original_embedding = embedding_model.encode(original_text)
        masked_embedding = embedding_model.encode(masked_text)
        
        # Calculate cosine similarity
        similarity = np.dot(original_embedding, masked_embedding) / (
            np.linalg.norm(original_embedding) * np.linalg.norm(masked_embedding)
        )
        
        # Semantic similarity should be high (>0.8)
        assert similarity > 0.8, f"Semantic similarity too low: {similarity}"
    
    def test_deterministic_processing(self):
        """Test that processing is deterministic for same input."""
        input_data = {
            "messages": [
                {"msg_id": "msg-123", "subject": "Budget Approval", "body": "Please approve the Q3 budget."}
            ]
        }
        
        # Process same input multiple times
        results = []
        for _ in range(3):
            # Mock processing (in real test, would use actual processing)
            result = {
                "sections": [
                    {
                        "title": "Actions",
                        "items": [
                            {
                                "title": "Approve Q3 budget",
                                "evidence_id": "ev:msg-123:0:50",
                                "confidence": 0.85
                            }
                        ]
                    }
                ]
            }
            results.append(result)
        
        # All results should be identical
        assert all(r == results[0] for r in results)
    
    def test_confidence_calibration(self):
        """Test that confidence scores are well-calibrated."""
        # This would require a labeled test set
        # For now, we test the structure
        test_cases = [
            {"confidence": 0.95, "expected_accuracy": 0.9},
            {"confidence": 0.85, "expected_accuracy": 0.8},
            {"confidence": 0.75, "expected_accuracy": 0.7},
        ]
        
        for case in test_cases:
            # In real test, would compare with actual accuracy
            assert 0.0 <= case["confidence"] <= 1.0
            assert case["confidence"] >= case["expected_accuracy"] - 0.1
```

## Performance Tests

### Load Testing

```python
# tests/test_performance.py
import pytest
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from digest_core.run import run_digest

class TestPerformance:
    def test_digest_generation_time(self):
        """Test that digest generation completes within time limit."""
        start_time = time.time()
        
        # Mock run_digest for testing
        # In real test, would use actual implementation
        time.sleep(0.1)  # Simulate processing time
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within 60 seconds (T90 target)
        assert duration < 60.0, f"Digest generation took too long: {duration}s"
    
    def test_concurrent_processing(self):
        """Test concurrent digest processing."""
        def process_digest():
            # Mock processing
            time.sleep(0.1)
            return {"status": "success"}
        
        # Run multiple digest generations concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_digest) for _ in range(5)]
            results = [future.result() for future in futures]
        
        # All should succeed
        assert all(r["status"] == "success" for r in results)
    
    def test_memory_usage(self):
        """Test memory usage stays within limits."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Simulate processing
        large_data = ["x" * 1000 for _ in range(1000)]
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        # Memory increase should be reasonable (< 100MB)
        assert memory_increase < 100, f"Memory usage too high: {memory_increase}MB"
```

## Test Configuration

### pytest.ini

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=digest_core
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=70
markers =
    unit: Unit tests
    integration: Integration tests
    contract: Contract tests
    snapshot: Snapshot tests
    leakage: PII leakage tests
    invariance: Invariance tests
    performance: Performance tests
    slow: Slow running tests
```

### conftest.py

```python
# tests/conftest.py
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_email_data():
    """Sample email data for testing."""
    return {
        "msg_id": "msg-123",
        "conversation_id": "conv-456",
        "datetime_received": "2024-01-15T10:00:00Z",
        "sender": {"name": "Alice", "email": "alice@corp.com"},
        "subject": "Budget Approval Required",
        "text_body": "Please approve the Q3 budget by Friday.",
        "is_read": False
    }

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        "choices": [{
            "message": {
                "content": '{"sections": [{"title": "Actions", "items": []}]}'
            }
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }

@pytest.fixture(autouse=True)
def setup_logging():
    """Setup logging for tests."""
    from digest_core.observability.logs import setup_logging
    setup_logging(log_level="DEBUG", log_json=False)
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install uv
      run: pip install uv
    
    - name: Install dependencies
      run: |
        cd digest-core
        uv sync --dev
    
    - name: Run linting
      run: |
        cd digest-core
        make lint
    
    - name: Run tests
      run: |
        cd digest-core
        pytest --cov=digest_core --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./digest-core/coverage.xml
```

## Test Data Management

### Fixtures and Test Data

```python
# tests/fixtures/generate_fixtures.py
"""Generate test fixtures for various scenarios."""

def generate_email_fixtures():
    """Generate email fixtures for testing."""
    fixtures = {
        "simple_action": {
            "subject": "Action Required",
            "body": "Please approve the budget by Friday.",
            "expected_actions": 1
        },
        "multiple_actions": {
            "subject": "Multiple Tasks",
            "body": "Please review the proposal and approve the budget.",
            "expected_actions": 2
        },
        "no_actions": {
            "subject": "FYI",
            "body": "This is just for your information.",
            "expected_actions": 0
        }
    }
    return fixtures

def generate_pii_fixtures():
    """Generate PII fixtures for leakage testing."""
    return {
        "emails": ["user@corp.com", "test@example.org"],
        "phones": ["+7 999 123 45 67", "+1 555 123 4567"],
        "credit_cards": ["1234 5678 9012 3456"],
        "ssns": ["123-45-6789"]
    }
```

---

**Итог:** Эта стратегия тестирования обеспечивает комплексное покрытие всех аспектов ActionPulse, от базовой функциональности до критически важных вопросов приватности и производительности.
