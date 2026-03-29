# digest-core

Python 3.11 package. Daily email digest pipeline: EWS → normalize → threads → evidence → LLM → assemble → deliver (MM DM).

## Commands

```bash
# Setup
uv sync                              # Install dependencies
make setup                           # Same via Makefile

# Development
make test                            # Run pytest (all mocked, no network needed)
make lint                            # Ruff + black
make format                          # Auto-fix lint issues
make smoke                           # Smoke test (dry-run)
make clean                           # Remove __pycache__, .pytest_cache, etc.

# Run
python -m digest_core.cli run                          # Full run (today, EWS + LLM + MM delivery)
python -m digest_core.cli run --dry-run                # Ingest + normalize only, no LLM
python -m digest_core.cli run --from-date 2026-03-28   # Specific date
python -m digest_core.cli run --window rolling_24h     # Last 24h instead of calendar day
python -m digest_core.cli run --out /tmp/digest --state /tmp/state  # Custom paths
python -m digest_core.cli diagnose                     # Environment diagnostics

# Docker
make docker                           # Build image
make docker-run                       # Run with env vars and volume mounts
```

## Architecture (8-stage pipeline)

```
1.INGEST (ews.py) → 2.NORMALIZE (html.py, quotes.py) → 3.THREADS (build.py)
→ 4.EVIDENCE (split.py, BUDGET OWNER ≤3000 tokens) → 5.SELECT (context.py)
→ 6.LLM (gateway.py, qwen3.5-397b, max 2 calls/run) → 7.ASSEMBLE (jsonout.py, markdown.py)
→ 8.DELIVER (mattermost.py, webhook/bot)
```

Full contracts in `docs/ARCHITECTURE.md §4`.

## Key Files

| File | Purpose |
|------|---------|
| `src/digest_core/cli.py` | Typer CLI entry point (`run`, `diagnose`) |
| `src/digest_core/run.py` | Pipeline orchestration (TD-001: needs refactor, copy-paste) |
| `src/digest_core/config.py` | Pydantic config (TD-003: YAML overwrites ENV — known bug) |
| `src/digest_core/llm/gateway.py` | LLM HTTP client (TD-011: needs 429/5xx retry) |
| `src/digest_core/llm/schemas.py` | Pydantic output schemas: Digest, Section, Item |
| `prompts/extract_actions.v1.j2` | Extraction prompt (TD-005: needs rewrite, 23 lines too minimal) |
| `configs/config.example.yaml` | Reference config |
| `docs/ARCHITECTURE.md` | **Source of truth** — all decisions, contracts, roadmap |

## Code Style

- Python 3.11, ruff (line-length=100), black, isort
- Typer for CLI, httpx for HTTP, structlog for JSON logs, pydantic for validation
- Prefer small testable modules. Each pipeline stage = separate file.

## Testing

```bash
make test    # All tests use mocks, run anywhere
```

- Tests in `tests/test_*.py` (13 files)
- Fixtures in `tests/fixtures/emails/` (10 email samples)
- Mock LLM in `tests/mock_llm_gateway.py`
- **Real EWS/LLM tests**: corp network only. Use replay mode for offline dev.

## Gotchas

- **`run.py:168` relative path**: `Path("prompts")` breaks outside `digest-core/` dir. Always `cd digest-core` before running. (TD-002, fix pending)
- **Config precedence bug (TD-003)**: YAML files overwrite ENV vars. If you set `EWS_PASSWORD` in `.env` but also have `ews:` in YAML, the YAML wins. Workaround: don't put EWS/LLM settings in YAML.
- **NormalizedMessage naming**: Output of Stage 1 (INGEST) is named `NormalizedMessage` but body is still raw HTML. Actual normalization happens in Stage 2. Don't be confused.
- **Idempotency**: If artifacts exist and are <48h old, pipeline skips. Delete `out/digest-*.json` to force re-run (or use `--force` when implemented).
- **Token estimation**: `words * 1.3` approximation, NOT tiktoken. Off by ~10% but fine for 3000-token budget.
- **LLM timeout**: Default 45s too low for qwen3.5-397b (TD-013). Bump to 120 in config.
- **Prompt files are `.j2` but NOT Jinja2**: Loaded via `.read_text()`, no template engine (ADR-009).

## Environment Variables

```bash
# Required
EWS_PASSWORD=...          # Exchange NTLM password
LLM_TOKEN=...             # LLM Gateway bearer token

# Required for MM delivery
MM_WEBHOOK_URL=...        # Mattermost incoming webhook URL

# Optional
DIGEST_CONFIG_PATH=...    # Custom config YAML path
DIGEST_OUT_DIR=...        # Override output directory
DIGEST_STATE_DIR=...      # Override state directory
```

## Offline Development (outside corp network)

EWS and LLM Gateway are only accessible from corp network.

```bash
# Inside corp: capture snapshot
python -m digest_core.cli run --dump-ingest /tmp/ews-snapshot.json

# Outside corp: replay without EWS
python -m digest_core.cli run --replay-ingest /tmp/ews-snapshot.json

# Diagnostics: export and send via MM
python -m digest_core.cli export-diagnostics --trace-id <id> --send-mm
```

## Active Tech Debt (Phase 0)

| ID | What | Severity |
|----|------|----------|
| TD-005 | Prompt too minimal (23 lines) | Critical |
| TD-002 | Relative prompt path | High |
| TD-003 | Config: YAML overwrites ENV | High |
| TD-004 | No graceful LLM degradation | High |
| TD-011 | No HTTP 429/5xx retry | High |

Full list: `docs/ARCHITECTURE.md §13`
