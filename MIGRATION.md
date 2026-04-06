# Schema migration notes (V2 → V3)

This document accompanies release **1.1.0** (see [`CHANGELOG.md`](./CHANGELOG.md)).

## What changed

- **Removed** local PII masking (`digest_core/privacy/`, `*_masked` fields, `owners_masked`, etc.).
- **`EnhancedDigestV3`** (Pydantic in `digest_core/llm/schemas.py`) uses **plain** `owners` / `participants` and declares `schema_version: "3.0"` with default `prompt_version: "mvp.5"`.
- That V3 shape is consumed by the LLM gateway’s **summarization / `process_digest`** path when `prompt_version="mvp.5"` (Jinja templates under `prompts/summarize/`), **not** by the default daily CLI extraction prompt.

## Default daily CLI (`digest_core.cli run`)

The production pipeline in `digest_core/run.py` builds a **`Digest`** object with:

- `schema_version="1.0"`
- `prompt_version` such as `extract_actions.v1` / `extract_actions.en.v1` (plain-text prompts under `prompts/`)

Output JSON is **`sections` / `items`** with `evidence_id`, `source_ref`, optional `citations`, etc., as defined on `Digest`, `Section`, and `Item` in `llm/schemas.py`.

If you only consume that JSON/Markdown from `run`, you do **not** need to migrate to `EnhancedDigestV3` unless you call the separate gateway API path that returns the V3 shape.

## Legacy V2 artifacts

Older stored digests that still use masked fields may render via backward-compatible code paths mentioned in `CHANGELOG.md` §1.1.0. When re-running the pipeline, new artifacts follow the current `Digest` / gateway contracts above.
