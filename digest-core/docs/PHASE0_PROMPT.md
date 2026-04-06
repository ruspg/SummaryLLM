# Phase 0 Implementation Prompt

> **🗄️ HISTORICAL — Phase 0 was completed in 2026-03.** Этот документ —
> исходный execution-промпт для Phase 0 hardening (TD-001 ... TD-013, Stage 8,
> offline tooling, E2E tests). Все упомянутые задачи уже реализованы и
> зафиксированы в [`ARCHITECTURE.md` §13.1](./ARCHITECTURE.md). Например,
> упоминания `extract_actions.v1.j2` ниже относятся к **завершённому**
> переименованию `.j2 → .txt` (TD-010).
>
> Не используйте этот файл как чек-лист текущей работы. Для актуального
> состояния технического долга см. `ARCHITECTURE.md §13.2`.

> Copy-paste this into a new Claude Code session to start executing Phase 0 backlog.

---

You are working on **ActionPulse** — a daily corporate email digest tool that extracts actionable items from Exchange emails using an LLM (qwen35-397b-a17b) and delivers the digest to Mattermost DM.

## Before you start

1. Read `CLAUDE.md` (root) and `digest-core/CLAUDE.md` — they contain commands, gotchas, and key constraints.
2. Read `digest-core/docs/ARCHITECTURE.md` — this is the **single source of truth** for all architecture decisions, contracts, and the roadmap. Every code change must align with this document.
3. Run `cd digest-core && make test` to confirm the baseline is green before making changes.

## What exists

The MVP pipeline is **fully connected end-to-end** (8 stages: ingest → normalize → threads → evidence → select → LLM → assemble → deliver). All stages have working code, tests, and Pydantic schemas. What's missing is hardening, a proper prompt, delivery to Mattermost, and offline dev tooling.

## Your mission: Phase 0 — MVP Hardening + MM Delivery

Execute the tasks below **in the recommended order**. Each task is a separate commit. Run `make test` after each change to confirm nothing breaks. Create a feature branch per logical group (or one branch for all Phase 0 if preferred).

### Execution order (optimized for dependencies)

**Batch 1 — Quick wins, unblock other work (do first):**

1. **[TD-013] Bump timeout_s 45→120** (0.5h)
   - File: `src/digest_core/config.py` — change `timeout_s` default from 45 to 120 in `LLMConfig`
   - File: `configs/config.example.yaml` — update `timeout_s: 120`
   - Why first: trivial change, unblocks real LLM testing with qwen35-397b-a17b

2. **[TD-002] Fix prompt path resolution** (1h)
   - File: `src/digest_core/run.py` line ~168 — `Path("prompts")` is relative, breaks outside `digest-core/`
   - Fix: use `Path(__file__).parent.parent.parent / "prompts"` to resolve relative to package root
   - Test: `python -m digest_core.cli run --dry-run` must work from repo root, not just from `digest-core/`

3. **[TD-010] Rename .j2 → .txt, delete dead prompts** (0.5h)
   - Rename: `prompts/extract_actions.v1.j2` → `extract_actions.v1.txt`
   - Rename: `prompts/extract_actions.en.v1.j2` → `extract_actions.en.v1.txt`
   - Delete: `prompts/summarize.v1.j2` and `prompts/summarize.en.v1.j2` (dead code, see ADR-001/ADR-009)
   - Update: `run.py` to reference new filenames
   - Commit together with TD-002 (same area of code)

**Batch 2 — Core resilience (do before feature work):**

4. **[TD-001] Refactor run.py — eliminate copy-paste** (2h)
   - Merge `run_digest()` and `run_digest_dry_run()` into single `_run_pipeline(dry_run: bool)` function
   - Extract shared setup: config loading, logging init, metrics, health server, date parsing, idempotency check
   - This refactor makes subsequent changes (graceful degradation, MM delivery, replay mode) much cleaner
   - Add `--force` flag to CLI at the same time (bypass T-48h idempotency check)

5. **[TD-003] Fix config precedence** (1.5h)
   - Problem: `_apply_yaml_config()` replaces entire sub-config objects, overwriting ENV vars
   - Fix: merge YAML dicts into defaults *before* pydantic-settings init, or use deep dict merge instead of object replacement
   - Also add `rate_limit_rpm: int = 15` field to `LLMConfig` (TD-012)
   - Test: set `EWS_PASSWORD` in env + have `ews:` section in YAML → ENV must win

6. **[TD-011] Add HTTP 429/5xx retry to LLM gateway** (2h)
   - File: `src/digest_core/llm/gateway.py`
   - Add to `_make_request_with_retry`: retry on `httpx.HTTPStatusError` where status is 429 or 5xx
   - HTTP 429: wait `Retry-After` header value (or 60s default), then 1 retry
   - HTTP 5xx: wait 5s, then 1 retry
   - Minimum 4s between any LLM calls (respect 15 RPM rate limit)
   - Max 2 total LLM calls per pipeline run (1 primary + 1 retry of any kind)
   - Use tenacity retry conditions, not manual loops

7. **[TD-004] Graceful LLM degradation** (2h)
   - In the refactored `_run_pipeline()`: wrap the LLM stage in try/except
   - On any LLM failure after retries: create a valid `Digest` with a "Статус" section containing error banner
   - Write JSON/MD artifacts with the partial report (stages 1-5 data is still valid)
   - Pipeline exit code = 0 (partial success), log warning
   - See ARCHITECTURE.md §8 Error Taxonomy for the exact partial report JSON format

**Batch 3 — The prompt (highest impact single task):**

8. **[TD-005] Rewrite extract_actions prompt** (4h)
   - File: `prompts/extract_actions.v1.txt` (after rename in step 3)
   - This is the **most important task** — prompt quality is 80% of the product (principle P7)
   - Target: 80-150 lines. Current: 23 lines (too minimal)
   - Must include:
     - Clear section taxonomy: "Мои действия" (actionable requests), "Срочное" (deadlines ≤2 business days), "К сведению" (FYI, no action required)
     - 2-3 few-shot examples with RU email evidence → correct JSON output
     - Explicit evidence_id mapping instructions (use the exact IDs from input)
     - source_ref construction rules: `{"type": "email", "msg_id": "<from evidence>"}`
     - Confidence calibration: 0.9+ = explicit request with deadline, 0.7-0.9 = clear action, 0.5-0.7 = implied, <0.5 = weak signal
     - Edge cases: empty evidence → empty sections; unclear actions → skip; multiple actions in one chunk → multiple items
     - Output language: Russian for titles and content
     - Strict JSON only, no text outside JSON
   - Also update EN variant (`extract_actions.en.v1.txt`) with same structure
   - See ARCHITECTURE.md §9.3 for full section taxonomy spec

**Batch 4 — Delivery + offline dev tooling:**

9. **Implement Mattermost DM delivery (Stage 8)** (5h)
   - Create `src/digest_core/deliver/__init__.py` and `src/digest_core/deliver/mattermost.py`
   - Add `DeliverConfig` with `MattermostDeliverConfig` to `config.py`:
     - `enabled: bool`, `webhook_url_env: str = "MM_WEBHOOK_URL"`, `max_message_length: int = 16383`, `include_trace_footer: bool = True`
   - MM markdown formatter: compact format (no `###` headings, no evidence section — see ARCHITECTURE.md §4.2 Stage 8 for format example)
   - Message splitting if >16383 chars
   - Wire into `_run_pipeline()` after assemble stage
   - **Delivery failure = warning log, exit code 0** (ADR-011). File artifacts already saved.
   - Add `MM_WEBHOOK_URL` to `.env.example` and `configs/config.example.yaml`
   - Test: mock webhook endpoint, verify POST body format

10. **Implement EWS replay mode** (3h)
    - Add CLI flags: `--dump-ingest <path>` and `--replay-ingest <path>`
    - `--dump-ingest`: after EWS fetch + normalize, serialize `List[NormalizedMessage]` to JSON file
    - `--replay-ingest`: skip EWS entirely, load messages from JSON snapshot
    - Snapshot format: JSON array with metadata header (fetch timestamp, count, source)
    - Privacy note: snapshot contains real email content — do NOT include in diagnostic bundles
    - This enables "Code outside, run inside, debug outside" workflow (ADR-012)

11. **Implement export-diagnostics CLI command** (4h)
    - New CLI command: `python -m digest_core.cli export-diagnostics --trace-id <id> --out <dir>`
    - Bundle contents (all PII-redacted): run.log, artifacts, pipeline-metrics.json, evidence-summary.json (stats only, NO content), config-sanitized.yaml, llm-request-trace.json (metadata only), env-info.txt
    - See ARCHITECTURE.md §17.3 for full bundle spec
    - Optional `--send-mm` flag: upload .tar.gz to MM DM via webhook

**Batch 5 — Verification:**

12. **E2E smoke test with mock LLM** (3h)
    - Create `tests/test_e2e_pipeline.py`
    - Exercise full pipeline: fixture emails → all 8 stages → valid JSON + MD + MM delivery mock
    - Assert: schema valid, sections match taxonomy, evidence_ids exist, MM webhook called
    - Test dry-run mode: no LLM calls, no delivery
    - Test graceful degradation: mock LLM returns 500 → partial report generated
    - Test replay mode: `--replay-ingest` with fixture snapshot

## Key constraints to remember

- **LLM model:** qwen35-397b-a17b, 15 RPM rate limit. Max 2 LLM calls per run. Temperature 0.1.
- **Network:** EWS and LLM Gateway only accessible from corp network. MM accessible from everywhere. All CI tests use mocks.
- **Output language:** Russian for digest content, section titles, error messages.
- **Code style:** Python 3.11, ruff (line-length=100), black, structlog for logging, httpx for HTTP, pydantic for validation.
- **No new dependencies** unless absolutely necessary. The existing stack (httpx, tenacity, structlog, pydantic) covers everything.
- **Don't touch** stages 2-5 (normalize, threads, evidence, select) — they work fine. Focus on stages 1 (path fix), 6 (retry/degradation), 7 (prompt), 8 (deliver), and CLI/config.

## Verification checklist (Phase 0 exit criteria)

- [ ] `make test` passes with all existing + new tests
- [ ] `python -m digest_core.cli run --dry-run` works from repo root (not just `digest-core/`)
- [ ] Prompt produces 3 sections (Мои действия / Срочное / К сведению) with valid evidence_ids
- [ ] LLM timeout → partial report with error banner (not crash)
- [ ] HTTP 429 → wait + retry (not immediate crash)
- [ ] MM webhook delivery: digest arrives in configured channel
- [ ] MM delivery failure → warning logged, pipeline succeeds, files saved
- [ ] `--replay-ingest` works with saved snapshot (offline pipeline run)
- [ ] `export-diagnostics` produces valid .tar.gz bundle
- [ ] Config: ENV vars always override YAML values
