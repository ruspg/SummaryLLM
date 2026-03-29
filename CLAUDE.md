# SummaryLLM

Daily corporate communications digest with LLM extraction. Privacy-first, evidence-traced.

## Repo Structure

```
digest-core/     # Python package — the actual product (see digest-core/CLAUDE.md)
scripts/         # Installation and setup scripts (install.sh, setup.sh)
```

Monorepo with one package. All development happens in `digest-core/`.

## Key Documents

- `digest-core/docs/ARCHITECTURE.md` — **Single source of truth** for architecture, contracts, ADRs, roadmap
- `digest-core/docs/Bus_Req_v5.md` — Business requirements (MVP → LVL5)
- `digest-core/docs/Tech_details_v1.md` — Original technical spec

## Language

- Code: English (variables, functions, comments)
- Output/prompts: Russian (дайджест is RU-first product)
- Docs: Russian for product docs, English for code-level docs

## Golden Rules

- Never log payloads or secrets. Structured logs only (structlog JSON).
- Every digest item MUST cite `evidence_id` and `source_ref` (principle P2: Traceability).
- Secrets via ENV only — never in YAML config files.
- Extract-over-Generate: LLM extracts from evidence, does not hallucinate (principle P1).
- Single LLM call per run — 15 RPM rate limit on qwen3.5-397b (ADR-008).

## Network Topology

- **EWS + LLM Gateway**: corp network only. Real tests only from inside.
- **Mattermost**: accessible from everywhere (delivery target).
- **Dev workflow**: "Code outside, run inside, debug outside" (ADR-012).
- Use `--dump-ingest` / `--replay-ingest` for offline development.
