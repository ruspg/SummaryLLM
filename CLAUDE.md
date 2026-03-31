# ActionPulse

Daily corporate communications digest with LLM extraction. Privacy-first, evidence-traced.

## Repo Structure

```
digest-core/     # Python package — the actual product (see digest-core/CLAUDE.md)
scripts/         # Installation and setup scripts (install.sh, setup.sh)
```

Monorepo with one package. All development happens in `digest-core/`.

## Key Documents

- `digest-core/docs/ARCHITECTURE.md` — **Single source of truth** for digest-core architecture, contracts, ADRs, roadmap (verify against code when in doubt)
- `digest-core/docs/PHASE0_PROMPT.md` — Historical Phase 0 execution checklist; not a guarantee that items are still open
- `docs/planning/BUSINESS_REQUIREMENTS.md` — Product / business requirements (repo root `docs/`)
- `docs/development/TECHNICAL.md` — Broader technical notes (may lag `digest-core`; prefer `ARCHITECTURE.md` for the Python package)

## Language

- Code: English (variables, functions, comments)
- Output/prompts: Russian (дайджест is RU-first product)
- Docs: Russian for product docs, English for code-level docs

## Golden Rules

- Never log payloads or secrets. Structured logs only (structlog JSON).
- Every digest item MUST cite `evidence_id` and `source_ref` (principle P2: Traceability).
- Secrets via ENV only — never in YAML config files.
- Extract-over-Generate: LLM extracts from evidence, does not hallucinate (principle P1).
- Max 2 LLM calls per run (1 primary + 1 quality retry), each with 1 internal retry for transient errors. 15 RPM rate limit on qwen35-397b-a17b (ADR-008).

## Network Topology

- **EWS + LLM Gateway**: corp network only. Real tests only from inside.
- **Mattermost**: accessible from everywhere (delivery target).
- **Dev workflow**: "Code outside, run inside, debug outside" (ADR-012).
- Use `--dump-ingest` / `--replay-ingest` for offline development.

## Git Preflight

- Always run `git fetch origin --prune` before implementation work, Plane updates, or PR creation.
- Work only from a real branch cut from current `origin/main`; never from detached `HEAD`.
- If the current worktree cannot fetch because git metadata is outside the writable sandbox, create a fresh clone/worktree inside the writable workspace and continue there.
- Do not update Plane or open a PR until the branch base and baseline checks are verified on the exact branch that will be used.
- If a PR was opened from stale `main`, close it and restack from fresh `origin/main` instead of trying to salvage bad history.
