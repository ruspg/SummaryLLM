# Code Examples

> ## ⚠️ Status: Иллюстративные примеры — не актуальные сигнатуры
>
> Этот документ содержит **иллюстративный** псевдо-код, написанный на раннем
> этапе планирования. Сигнатуры функций, имена параметров и поток управления
> **не совпадают** с актуальной реализацией. Конкретные расхождения, найденные
> при аудите 2026-04-06:
>
> - `model="corp/qwen35-397b-a17b"` → реальный default `"qwen35-397b-a17b"` (без
>   префикса `corp/`), см. [`cli.py:29`](../../digest-core/src/digest_core/cli.py).
> - `run_digest(from_date, sources, output_dir, model, dry_run, verbose, window, config)`
>   с возвратом `result` объекта (`result.success`, `result.output_files`, `result.error`)
>   → реальная сигнатура: `run_digest(from_date, sources, out, model, window, state, validate_citations=False, force=False, dump_ingest=None, replay_ingest=None, record_llm=None, replay_llm=None) -> bool`
>   (см. [`run.py:80`](../../digest-core/src/digest_core/run.py)). Параметра `verbose`
>   и параметра `config` нет; параметр зовётся `out`, а не `output_dir`.
> - Структура `LLMGatewayClient` ниже — упрощённая иллюстрация; реальный
>   `LLMGateway` в [`llm/gateway.py`](../../digest-core/src/digest_core/llm/gateway.py)
>   использует `tenacity.Retrying`, `RetryableLLMError`, rate-limit spacing
>   через `MIN_LLM_INTERVAL_SECONDS`, и quality retry на пустые секции.
>
> Используйте этот документ для **общего понимания подхода** (Typer-CLI,
> retry-логика, structlog), а не как источник для копирования. Канонический
> код — в `digest-core/src/digest_core/`.

Практические примеры кода для разработки ActionPulse с детальными объяснениями и best practices.

## CLI Implementation

### Typer CLI Setup

```python
# src/digest_core/cli.py
import typer
from typing import Optional, List
from pathlib import Path
from digest_core.run import run_digest
from digest_core.config import Config

app = typer.Typer(
    name="digest-core",
    help="ActionPulse Digest Core - Daily corporate communications digest",
    add_completion=False
)

@app.command()
def run(
    from_date: str = typer.Option("today", help="Date to process (YYYY-MM-DD or 'today')"),
    sources: str = typer.Option("ews", help="Comma-separated list of sources"),
    out: Path = typer.Option("./out", help="Output directory"),
    model: str = typer.Option("corp/qwen35-397b-a17b", help="LLM model to use"),
    dry_run: bool = typer.Option(False, help="Run without LLM calls"),
    verbose: bool = typer.Option(False, help="Verbose output"),
    window: str = typer.Option("calendar_day", help="Time window type")
):
    """Run digest generation for specified date and sources."""
    try:
        config = Config()
        sources_list = sources.split(",")
        
        result = run_digest(
            from_date=from_date,
            sources=sources_list,
            output_dir=out,
            model=model,
            dry_run=dry_run,
            verbose=verbose,
            window=window,
            config=config
        )
        
        if result.success:
            typer.echo(f"✅ Digest generated successfully: {result.output_files}")
            raise typer.Exit(0)
        else:
            typer.echo(f"❌ Digest generation failed: {result.error}")
            raise typer.Exit(1)
            
    except Exception as e:
        typer.echo(f"💥 Unexpected error: {e}")
        raise typer.Exit(1)

@app.command()
def validate_config():
    """Validate configuration files."""
    try:
        config = Config()
        typer.echo("✅ Configuration is valid")
        typer.echo(f"EWS Endpoint: {config.ews.endpoint}")
        typer.echo(f"LLM Model: {config.llm.model}")
    except Exception as e:
        typer.echo(f"❌ Configuration error: {e}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
```

## LLM Gateway Client

### HTTP Client with Retry Logic

```python
# src/digest_core/llm/gateway.py
import httpx
import uuid
import time
import json
from typing import Dict, Any, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from structlog import get_logger

logger = get_logger(__name__)

class LLMGatewayError(Exception):
    """Base exception for LLM Gateway errors."""
    pass

class LLMGatewayClient:
    def __init__(
        self,
        endpoint: str,
        headers: Dict[str, str],
        model: str,
        timeout_s: int = 120,
        max_retries: int = 3
    ):
        self.endpoint = endpoint
        self.headers = headers
        self.model = model
        self.timeout = httpx.Timeout(timeout_s)
        self.max_retries = max_retries

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send chat request to LLM Gateway with retry logic.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dict containing response data, trace_id, and metadata
        """
        trace_id = str(uuid.uuid4())
        request_headers = {
            **self.headers,
            "x-trace-id": trace_id,
            "x-request-id": str(uuid.uuid4())
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
            
        start_time = time.perf_counter()
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.endpoint,
                    headers=request_headers,
                    json=payload
                )
                
            latency_ms = int(1000 * (time.perf_counter() - start_time))
            response.raise_for_status()
            
            data = response.json()
            
            # Extract usage information if available
            usage = data.get("usage", {})
            
            result = {
                "trace_id": trace_id,
                "latency_ms": latency_ms,
                "data": data,
                "usage": {
                    "tokens_in": usage.get("prompt_tokens", 0),
                    "tokens_out": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                }
            }
            
            logger.info(
                "LLM request completed",
                trace_id=trace_id,
                latency_ms=latency_ms,
                tokens_in=result["usage"]["tokens_in"],
                tokens_out=result["usage"]["tokens_out"]
            )
            
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "LLM Gateway HTTP error",
                trace_id=trace_id,
                status_code=e.response.status_code,
                error=str(e)
            )
            raise LLMGatewayError(f"HTTP {e.response.status_code}: {e}")
            
        except httpx.TimeoutException:
            logger.error("LLM Gateway timeout", trace_id=trace_id)
            raise LLMGatewayError("Request timeout")
            
        except Exception as e:
            logger.error("LLM Gateway unexpected error", trace_id=trace_id, error=str(e))
            raise LLMGatewayError(f"Unexpected error: {e}")

    def extract_actions(
        self,
        evidence_texts: List[str],
        prompt_template: str
    ) -> Dict[str, Any]:
        """
        Extract action items from evidence texts.
        
        Args:
            evidence_texts: List of evidence text fragments
            prompt_template: Jinja2 template for the prompt
            
        Returns:
            Parsed JSON response with action items
        """
        # Prepare context for prompt
        context = {
            "evidence_texts": evidence_texts,
            "timestamp": time.time()
        }
        
        # Render prompt
        from jinja2 import Template
        template = Template(prompt_template)
        prompt = template.render(**context)
        
        messages = [
            {"role": "system", "content": "You are an expert at extracting actionable items from corporate communications."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.chat(messages, temperature=0.1, max_tokens=2000)
        
        # Parse and validate response
        try:
            content = response["data"]["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error("Failed to parse LLM response", error=str(e), content=content)
            raise LLMGatewayError(f"Invalid response format: {e}")
```

## Pydantic Models

### Data Models with Validation

```python
# src/digest_core/llm/schemas.py
from pydantic import BaseModel, Field, validator, AwareDatetime
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SourceType(str, Enum):
    EMAIL = "email"
    MATTERMOST_PUBLIC = "mm-public"
    MATTERMOST_DM = "mm-dm"

class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class SourceRef(BaseModel):
    """Reference to the source message."""
    type: SourceType
    msg_id: str
    conversation_id: Optional[str] = None
    channel: Optional[str] = None
    team: Optional[str] = None
    permalink: Optional[str] = None

class ActionItem(BaseModel):
    """Individual action item extracted from communications."""
    title: str = Field(..., min_length=1, max_length=500)
    owners_masked: List[str] = Field(default_factory=list)
    due: Optional[str] = None
    evidence_id: str = Field(..., regex=r"^ev:[a-f0-9]+:\d+:\d+$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_ref: SourceRef
    priority: Optional[ConfidenceLevel] = None
    tags: List[str] = Field(default_factory=list)
    
    @validator('due')
    def validate_due_date(cls, v):
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('due must be a valid ISO date string')
        return v

class Section(BaseModel):
    """Section of the digest containing related items."""
    title: str = Field(..., min_length=1, max_length=100)
    items: List[ActionItem] = Field(default_factory=list)
    summary: Optional[str] = None

class DigestMetadata(BaseModel):
    """Metadata about the digest generation."""
    digest_date: str = Field(..., regex=r"^\d{4}-\d{2}-\d{2}$")
    generated_at: AwareDatetime
    trace_id: str = Field(..., min_length=1)
    pipeline_version: str = Field(default="1.0.0")
    prompt_version: str = Field(default="extract_actions.v1")
    model_id: str
    sources_processed: List[str] = Field(default_factory=list)
    processing_stats: Dict[str, Any] = Field(default_factory=dict)

class Digest(BaseModel):
    """Complete digest structure."""
    metadata: DigestMetadata
    sections: List[Section] = Field(default_factory=list)
    
    @validator('sections')
    def validate_sections_not_empty(cls, v):
        if not v:
            raise ValueError('Digest must have at least one section')
        return v
    
    def to_markdown(self) -> str:
        """Convert digest to Markdown format."""
        lines = [f"# Дайджест — {self.metadata.digest_date}"]
        lines.append("")
        
        for section in self.sections:
            lines.append(f"## {section.title}")
            
            if section.summary:
                lines.append(section.summary)
                lines.append("")
            
            for item in section.items:
                item_lines = [f"- {item.title}"]
                
                if item.due:
                    item_lines[0] += f" — до **{item.due}**"
                
                if item.owners_masked:
                    owners = ", ".join(item.owners_masked)
                    item_lines[0] += f". Ответственные: {owners}"
                
                # Add source reference
                source_info = self._format_source_ref(item.source_ref)
                item_lines.append(f"  Источник: {source_info}, evidence {item.evidence_id}")
                
                lines.extend(item_lines)
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_source_ref(self, source_ref: SourceRef) -> str:
        """Format source reference for display."""
        if source_ref.type == SourceType.EMAIL:
            return f"письмо «{source_ref.msg_id}»"
        elif source_ref.type == SourceType.MATTERMOST_PUBLIC:
            return f"канал {source_ref.channel}"
        elif source_ref.type == SourceType.MATTERMOST_DM:
            return f"DM с {source_ref.channel}"
        else:
            return f"{source_ref.type}: {source_ref.msg_id}"

# Example usage
def create_sample_digest() -> Digest:
    """Create a sample digest for testing."""
    metadata = DigestMetadata(
        digest_date="2024-01-15",
        generated_at=datetime.now(),
        trace_id="abc123-def456",
        model_id="corp/qwen35-397b-a17b"
    )
    
    action_item = ActionItem(
        title="Утвердить лимиты Q3",
        owners_masked=["[[REDACT:NAME;id=9b3e]]"],
        due="2024-01-17",
        evidence_id="ev:msghash:1024:480",
        confidence=0.86,
        source_ref=SourceRef(
            type=SourceType.EMAIL,
            msg_id="urn:ews:...",
            conversation_id="conv123"
        )
    )
    
    section = Section(
        title="Мои действия",
        items=[action_item]
    )
    
    return Digest(
        metadata=metadata,
        sections=[section]
    )
```

## EWS Integration

### Exchange Web Services Client

```python
# src/digest_core/ingest/ews.py
from exchangelib import Credentials, Account, Configuration, DELEGATE, NTLM
from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import ssl
from structlog import get_logger

logger = get_logger(__name__)

class EWSClient:
    def __init__(
        self,
        endpoint: str,
        username: str,
        password: str,
        ca_cert_path: Optional[str] = None
    ):
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.ca_cert_path = ca_cert_path
        self._account = None
        
    def connect(self) -> Account:
        """Establish connection to Exchange server."""
        try:
            # Configure SSL if CA certificate is provided
            if self.ca_cert_path:
                BaseProtocol.HTTP_ADAPTER_CLS = NoVerifyHTTPAdapter
                ssl_context = ssl.create_default_context(cafile=self.ca_cert_path)
                BaseProtocol.HTTP_ADAPTER_CLS.ssl_context = ssl_context
            
            credentials = Credentials(
                username=self.username,
                password=self.password
            )
            
            config = Configuration(
                server=self.endpoint,
                credentials=credentials,
                auth_type=NTLM
            )
            
            self._account = Account(
                primary_smtp_address=self.username,
                credentials=credentials,
                config=config,
                autodiscover=False,
                access_type=DELEGATE
            )
            
            logger.info("EWS connection established", username=self.username)
            return self._account
            
        except Exception as e:
            logger.error("EWS connection failed", error=str(e))
            raise
    
    def get_messages(
        self,
        folder_name: str = "Inbox",
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages from specified folder.
        
        Args:
            folder_name: Name of the folder to search
            since: Only get messages after this datetime
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        if not self._account:
            self.connect()
        
        try:
            # Get folder
            folder = getattr(self._account, folder_name)
            
            # Build filter
            filter_kwargs = {}
            if since:
                filter_kwargs['datetime_received__gte'] = since
            
            # Query messages
            messages = folder.filter(**filter_kwargs).order_by('-datetime_received')[:limit]
            
            result = []
            for msg in messages:
                message_dict = {
                    'msg_id': str(msg.id),
                    'conversation_id': str(msg.conversation_id),
                    'datetime_received': msg.datetime_received.isoformat(),
                    'sender': {
                        'name': msg.sender.name,
                        'email': msg.sender.email_address
                    },
                    'subject': msg.subject,
                    'text_body': msg.text_body,
                    'is_read': msg.is_read,
                    'importance': msg.importance,
                    'has_attachments': msg.has_attachments,
                    'size': msg.size
                }
                result.append(message_dict)
            
            logger.info(
                "Messages retrieved",
                folder=folder_name,
                count=len(result),
                since=since.isoformat() if since else None
            )
            
            return result
            
        except Exception as e:
            logger.error("Failed to retrieve messages", error=str(e))
            raise
    
    def get_recent_messages(
        self,
        hours: int = 24,
        folder_name: str = "Inbox",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get messages from the last N hours."""
        since = datetime.now() - timedelta(hours=hours)
        return self.get_messages(folder_name=folder_name, since=since, limit=limit)
```

## Configuration Management

### Pydantic Settings

```python
# src/digest_core/config.py
from pydantic import BaseSettings, Field, validator
from typing import List, Optional, Dict, Any
from pathlib import Path

class EWSSettings(BaseSettings):
    endpoint: str = Field(..., env="EWS_ENDPOINT")
    user_upn: str = Field(..., env="EWS_USER_UPN")
    password_env: str = Field("EWS_PASSWORD", env="EWS_PASSWORD_ENV")
    verify_ca: Optional[str] = Field(None, env="EWS_CA_CERT")
    autodiscover: bool = Field(False)
    folders: List[str] = Field(["Inbox"])
    lookback_hours: int = Field(24, ge=1, le=168)
    page_size: int = Field(100, ge=10, le=1000)
    sync_state_path: str = Field(".state/ews.syncstate")
    
    @property
    def password(self) -> str:
        """Get password from environment variable."""
        import os
        return os.getenv(self.password_env, "")

class LLMSettings(BaseSettings):
    endpoint: str = Field(..., env="LLM_ENDPOINT")
    model: str = Field("corp/qwen35-397b-a17b")
    timeout_s: int = Field(45, ge=10, le=300)
    headers: Dict[str, str] = Field(default_factory=dict)
    max_tokens_per_run: int = Field(30000, ge=1000, le=100000)
    cost_limit_per_run: float = Field(5.0, ge=0.1, le=100.0)
    
    @validator('headers', pre=True)
    def validate_headers(cls, v):
        if isinstance(v, dict):
            return v
        # Handle environment variable substitution
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            import os
            var_name = v[2:-1]
            return {"Authorization": f"Bearer {os.getenv(var_name, '')}"}
        return {}

class ObservabilitySettings(BaseSettings):
    prometheus_port: int = Field(9108, ge=1024, le=65535)
    log_level: str = Field("INFO")
    log_json: bool = Field(True)
    log_payloads: bool = Field(False)

class Config(BaseSettings):
    """Main configuration class."""
    ews: EWSSettings = Field(default_factory=EWSSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def validate(self) -> bool:
        """Validate configuration."""
        errors = []
        
        # Validate EWS settings
        if not self.ews.endpoint.startswith(('http://', 'https://')):
            errors.append("EWS endpoint must be a valid URL")
        
        if not self.ews.user_upn or '@' not in self.ews.user_upn:
            errors.append("EWS user UPN must be a valid email address")
        
        # Validate LLM settings
        if not self.llm.endpoint.startswith(('http://', 'https://')):
            errors.append("LLM endpoint must be a valid URL")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
        
        return True
```

## Error Handling and Logging

### Structured Logging Setup

```python
# src/digest_core/observability/logs.py
import structlog
import sys
from typing import Any, Dict
from datetime import datetime

def setup_logging(log_level: str = "INFO", log_json: bool = True):
    """Configure structured logging."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if log_json else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    import logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )

class DigestLogger:
    """Logger with digest-specific context."""
    
    def __init__(self, trace_id: str, digest_date: str):
        self.logger = structlog.get_logger()
        self.trace_id = trace_id
        self.digest_date = digest_date
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(
            message,
            trace_id=self.trace_id,
            digest_date=self.digest_date,
            **kwargs
        )
    
    def error(self, message: str, error: Exception = None, **kwargs):
        """Log error message with context."""
        extra = {"error": str(error)} if error else {}
        self.logger.error(
            message,
            trace_id=self.trace_id,
            digest_date=self.digest_date,
            **extra,
            **kwargs
        )
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(
            message,
            trace_id=self.trace_id,
            digest_date=self.digest_date,
            **kwargs
        )

# Example usage
def example_usage():
    logger = DigestLogger("abc123", "2024-01-15")
    
    logger.info("Starting digest generation", source="ews")
    
    try:
        # Some processing
        result = {"items": 5, "sections": 2}
        logger.info("Digest generation completed", **result)
    except Exception as e:
        logger.error("Digest generation failed", error=e)
        raise
```

---

**Итог:** Эти примеры кода демонстрируют лучшие практики для разработки ActionPulse, включая обработку ошибок, структурированное логирование, валидацию данных и интеграцию с внешними сервисами.
