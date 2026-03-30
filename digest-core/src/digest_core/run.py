"""
Main digest pipeline runner.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, Iterable, List, Sequence
import uuid

import structlog

from digest_core.assemble.markdown import MarkdownAssembler
from digest_core.config import Config
from digest_core.deliver.mattermost import MattermostDeliverer
from digest_core.evidence.split import EvidenceChunk, EvidenceSplitter
from digest_core.ingest.ews import EWSIngest, NormalizedMessage
from digest_core.llm.gateway import LLMGateway
from digest_core.llm.prompt_registry import get_prompt_template_path
from digest_core.llm.schemas import Digest
from digest_core.normalize.html import HTMLNormalizer
from digest_core.normalize.quotes import QuoteCleaner
from digest_core.observability.healthz import start_health_server
from digest_core.observability.logs import setup_logging
from digest_core.observability.metrics import MetricsCollector
from digest_core.select.context import ContextSelector
from digest_core.threads.build import ThreadBuilder


PIPELINE_VERSION = "1.1.0"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PACKAGE_ROOT / "prompts"
SECTION_ORDER = {"Мои действия": 0, "Срочное": 1, "К сведению": 2}

logger = structlog.get_logger()


def run_digest(
    from_date: str,
    sources: List[str],
    out: str,
    model: str,
    window: str,
    state: str | None,
    validate_citations: bool = False,
    force: bool = False,
    dump_ingest: str | None = None,
    replay_ingest: str | None = None,
) -> bool:
    """Run the complete digest pipeline."""
    return _run_pipeline(
        from_date=from_date,
        sources=sources,
        out=out,
        model=model,
        window=window,
        state=state,
        validate_citations=validate_citations,
        dry_run=False,
        force=force,
        dump_ingest=dump_ingest,
        replay_ingest=replay_ingest,
    )


def run_digest_dry_run(
    from_date: str,
    sources: List[str],
    out: str,
    model: str,
    window: str,
    state: str | None,
    validate_citations: bool = False,
    force: bool = False,
    dump_ingest: str | None = None,
    replay_ingest: str | None = None,
) -> None:
    """Run the pipeline up to context selection without LLM or delivery."""
    _run_pipeline(
        from_date=from_date,
        sources=sources,
        out=out,
        model=model,
        window=window,
        state=state,
        validate_citations=validate_citations,
        dry_run=True,
        force=force,
        dump_ingest=dump_ingest,
        replay_ingest=replay_ingest,
    )


def _run_pipeline(
    *,
    from_date: str,
    sources: Sequence[str],
    out: str,
    model: str,
    window: str,
    state: str | None,
    validate_citations: bool,
    dry_run: bool,
    force: bool,
    dump_ingest: str | None,
    replay_ingest: str | None,
) -> bool:
    """Run the digest pipeline with shared setup for normal and dry-run modes."""
    trace_id = str(uuid.uuid4())
    log_file = setup_logging()

    config = Config()
    if model:
        config.llm.model = model
    if window in ("calendar_day", "rolling_24h"):
        config.time.window = window
    if state:
        state_dir = Path(state).expanduser()
        state_dir.mkdir(parents=True, exist_ok=True)
        config.ews.sync_state_path = str(
            state_dir / Path(config.ews.sync_state_path).name
        )

    metrics = MetricsCollector(config.observability.prometheus_port)
    start_health_server(port=9109, llm_config=config.llm)

    digest_date = _resolve_digest_date(from_date)
    output_dir = Path(out).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"digest-{digest_date}.json"
    md_path = output_dir / f"digest-{digest_date}.md"
    metadata_path = output_dir / f"trace-{trace_id}.meta.json"

    run_meta: Dict[str, Any] = {
        "trace_id": trace_id,
        "pipeline_version": PIPELINE_VERSION,
        "digest_date": digest_date,
        "dry_run": dry_run,
        "validate_citations": validate_citations,
        "log_file": str(log_file) if log_file else None,
        "output_dir": str(output_dir),
        "artifact_paths": {"json": str(json_path), "md": str(md_path)},
        "stage_durations_ms": {},
        "pipeline_metrics": {},
        "evidence_summary": {},
        "ews_fetch_stats": {},
        "llm_request_trace": {},
        "config_sanitized": _sanitize_config(config),
        "status": "started",
        "partial": False,
    }

    if not force and _should_skip_existing_artifacts(json_path, md_path):
        artifact_age_hours = _artifact_age_hours(json_path)
        logger.info(
            "Existing artifacts found within T-48h window, skipping rebuild",
            digest_date=digest_date,
            artifact_age_hours=artifact_age_hours,
            trace_id=trace_id,
        )
        metrics.record_run_total("ok")
        run_meta["status"] = "skipped"
        run_meta["pipeline_metrics"] = {"artifact_age_hours": artifact_age_hours}
        _write_json(metadata_path, run_meta)
        return True

    logger.info(
        "Starting digest run",
        trace_id=trace_id,
        digest_date=digest_date,
        dry_run=dry_run,
        sources=list(sources),
        replay_ingest=replay_ingest,
        dump_ingest=dump_ingest,
        force=force,
    )

    messages: List[NormalizedMessage]
    normalized_messages: List[NormalizedMessage]
    threads = []
    evidence_chunks: List[EvidenceChunk] = []
    selected_evidence: List[EvidenceChunk] = []

    try:
        if replay_ingest:
            replay_start = time.perf_counter()
            normalized_messages = _load_ingest_snapshot(
                Path(replay_ingest).expanduser()
            )
            messages = normalized_messages
            _record_stage_duration(run_meta, metrics, "ingest", replay_start)
            run_meta["ews_fetch_stats"] = {
                "source": "replay",
                "message_count": len(normalized_messages),
                "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            ingest_start = time.perf_counter()
            ingest = EWSIngest(config.ews, time_config=config.time, metrics=metrics)
            messages = ingest.fetch_messages(digest_date, config.time)
            metrics.record_emails_total(len(messages), "fetched")
            _record_stage_duration(run_meta, metrics, "ingest", ingest_start)
            run_meta["ews_fetch_stats"] = {
                "source": "ews",
                "message_count": len(messages),
                "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            normalize_start = time.perf_counter()
            normalized_messages = _normalize_messages(messages, config)
            _record_stage_duration(run_meta, metrics, "normalize", normalize_start)

        if dump_ingest:
            snapshot_path = Path(dump_ingest).expanduser()
            _dump_ingest_snapshot(snapshot_path, normalized_messages, digest_date)

        threads_start = time.perf_counter()
        thread_builder = ThreadBuilder()
        threads = thread_builder.build_threads(normalized_messages)
        _record_stage_duration(run_meta, metrics, "threads", threads_start)

        evidence_start = time.perf_counter()
        evidence_splitter = EvidenceSplitter(
            user_aliases=config.ews.user_aliases,
            user_timezone=config.time.user_timezone,
            context_budget_config=config.context_budget,
            chunking_config=config.chunking,
        )
        evidence_chunks = evidence_splitter.split_evidence(
            threads,
            total_emails=len(normalized_messages),
            total_threads=len(threads),
        )
        _record_stage_duration(run_meta, metrics, "evidence", evidence_start)

        select_start = time.perf_counter()
        context_selector = ContextSelector(
            buckets_config=config.selection_buckets,
            weights_config=config.selection_weights,
            context_budget_config=config.context_budget,
            shrink_config=config.shrink,
        )
        selected_evidence = context_selector.select_context(evidence_chunks)
        selection_metrics = context_selector.get_metrics()
        _record_stage_duration(run_meta, metrics, "select", select_start)

        run_meta["evidence_summary"] = _build_evidence_summary(
            threads=threads,
            evidence_chunks=evidence_chunks,
            selected_evidence=selected_evidence,
            selection_metrics=selection_metrics,
        )

        if dry_run:
            metrics.record_run_total("ok")
            metrics.record_digest_build_time()
            run_meta["status"] = "dry_run"
            run_meta["pipeline_metrics"] = {
                "emails_processed": len(normalized_messages),
                "threads_created": len(threads),
                "evidence_chunks": len(evidence_chunks),
                "selected_evidence": len(selected_evidence),
            }
            _write_json(metadata_path, run_meta)
            logger.info(
                "Digest dry-run completed successfully",
                trace_id=trace_id,
                digest_date=digest_date,
                emails_processed=len(normalized_messages),
                threads_created=len(threads),
                evidence_chunks=len(evidence_chunks),
                selected_evidence=len(selected_evidence),
            )
            return True

        llm_gateway = LLMGateway(config.llm, metrics=metrics)
        llm_stage_start = time.perf_counter()

        if not selected_evidence:
            digest = _build_empty_digest(digest_date, trace_id, prompt_version="none")
            llm_error = None
        else:
            prompt_version, prompt_text = _load_extract_prompt(config.llm.model)
            try:
                llm_response = llm_gateway.extract_actions(
                    evidence=selected_evidence,
                    prompt_template=prompt_text,
                    trace_id=trace_id,
                )
                digest = Digest(
                    schema_version="1.0",
                    prompt_version=prompt_version,
                    digest_date=digest_date,
                    trace_id=trace_id,
                    sections=_sort_sections(llm_response.get("sections", [])),
                )
                llm_error = None
            except Exception as exc:
                metrics.record_degradation("llm_failed")
                run_meta["partial"] = True
                run_meta["status"] = "partial"
                digest = _build_partial_digest(
                    digest_date=digest_date,
                    trace_id=trace_id,
                    error_message=str(exc),
                )
                llm_error = exc
                logger.warning(
                    "LLM stage failed after retries, writing partial digest",
                    trace_id=trace_id,
                    error=str(exc),
                )

        _record_stage_duration(run_meta, metrics, "llm", llm_stage_start)

        llm_meta = llm_gateway.get_request_stats()
        llm_trace = dict(getattr(llm_gateway, "last_request_meta", {}))
        llm_trace.update(
            {
                "model": llm_meta.get("model"),
                "latency_ms": llm_meta.get("last_latency_ms", 0),
                "timeout_s": llm_meta.get("timeout_s"),
            }
        )
        if llm_error is not None:
            llm_trace["error"] = str(llm_error)
        run_meta["llm_request_trace"] = llm_trace
        try:
            metrics.record_llm_latency(llm_meta.get("last_latency_ms", 0) or 0)
            metrics.record_llm_tokens(
                int(llm_trace.get("tokens_in", 0)), int(llm_trace.get("tokens_out", 0))
            )
        except Exception:
            pass

        assemble_start = time.perf_counter()
        _write_json(json_path, digest.model_dump(exclude_none=True))
        MarkdownAssembler().write_digest(digest, md_path)
        _record_stage_duration(run_meta, metrics, "assemble", assemble_start)

        delivery_receipt: Dict[str, Any] = {}
        if config.deliver.mattermost.enabled:
            deliver_start = time.perf_counter()
            try:
                delivery_receipt = MattermostDeliverer(
                    config.deliver.mattermost
                ).deliver_digest(digest)
            except Exception as exc:
                delivery_receipt = {"status": "warning", "error": str(exc)}
                logger.warning(
                    "Mattermost delivery failed", trace_id=trace_id, error=str(exc)
                )
            _record_stage_duration(run_meta, metrics, "deliver", deliver_start)
        run_meta["delivery_receipt"] = delivery_receipt

        metrics.record_run_total("ok")
        metrics.record_digest_build_time()
        run_meta["status"] = "ok" if not run_meta["partial"] else "partial"
        run_meta["pipeline_metrics"] = {
            "total_items": _count_digest_items(digest),
            "emails_processed": len(normalized_messages),
            "threads_created": len(threads),
            "evidence_chunks": len(evidence_chunks),
            "selected_evidence": len(selected_evidence),
        }
        _write_json(metadata_path, run_meta)

        logger.info(
            "Digest run completed",
            trace_id=trace_id,
            digest_date=digest_date,
            total_items=_count_digest_items(digest),
            partial=run_meta["partial"],
        )
        return True
    except Exception as exc:
        metrics.record_run_total("failed")
        run_meta["status"] = "failed"
        run_meta["error"] = str(exc)
        _write_json(metadata_path, run_meta)
        logger.error(
            "Digest run failed", trace_id=trace_id, error=str(exc), exc_info=True
        )
        raise


def _resolve_digest_date(from_date: str) -> str:
    if from_date == "today":
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    datetime.strptime(from_date, "%Y-%m-%d")
    return from_date


def _artifact_age_hours(path: Path) -> float:
    return (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 3600


def _should_skip_existing_artifacts(json_path: Path, md_path: Path) -> bool:
    if not json_path.exists() or not md_path.exists():
        return False
    return _artifact_age_hours(json_path) < 48


def _normalize_messages(
    messages: Sequence[NormalizedMessage], config: Config
) -> List[NormalizedMessage]:
    normalizer = HTMLNormalizer()
    quote_cleaner = QuoteCleaner(
        keep_top_quote_head=config.email_cleaner.keep_top_quote_head,
        config=config.email_cleaner,
    )

    normalized_messages = []
    for msg in messages:
        text_body, _ = normalizer.html_to_text(msg.text_body)
        text_body = normalizer.truncate_text(text_body, max_bytes=200000)
        if config.email_cleaner.enabled:
            cleaned_body, _ = quote_cleaner.clean_email_body(
                text_body, lang="auto", policy="standard"
            )
        else:
            cleaned_body = text_body

        normalized_messages.append(
            NormalizedMessage(
                msg_id=msg.msg_id,
                conversation_id=msg.conversation_id,
                datetime_received=msg.datetime_received,
                sender_email=msg.sender_email,
                subject=msg.subject,
                text_body=cleaned_body,
                to_recipients=msg.to_recipients,
                cc_recipients=msg.cc_recipients,
                importance=msg.importance,
                is_flagged=msg.is_flagged,
                has_attachments=msg.has_attachments,
                attachment_types=msg.attachment_types,
                from_email=msg.from_email,
                from_name=msg.from_name,
                to_emails=msg.to_emails,
                cc_emails=msg.cc_emails,
                message_id=msg.message_id,
                body_norm=cleaned_body,
                received_at=msg.received_at,
            )
        )
    return normalized_messages


def _load_extract_prompt(model_name: str) -> tuple[str, str]:
    model_lower = (model_name or "").lower()
    prompt_version = (
        "extract_actions.en.v1" if "qwen" in model_lower else "extract_actions.v1"
    )
    template_path = get_prompt_template_path(prompt_version)
    prompt_path = PROMPTS_DIR / template_path
    return prompt_version, prompt_path.read_text(encoding="utf-8")


def _build_empty_digest(digest_date: str, trace_id: str, prompt_version: str) -> Digest:
    return Digest(
        schema_version="1.0",
        prompt_version=prompt_version,
        digest_date=digest_date,
        trace_id=trace_id,
        sections=[],
    )


def _build_partial_digest(
    digest_date: str, trace_id: str, error_message: str
) -> Digest:
    title = "LLM Gateway недоступен. Дайджест неполный."
    if "timed out" in error_message.lower() or "timeout" in error_message.lower():
        title = "LLM Gateway превысил таймаут. Дайджест неполный."
    return Digest(
        schema_version="1.0",
        prompt_version="none",
        digest_date=digest_date,
        trace_id=trace_id,
        sections=[
            {
                "title": "Статус",
                "items": [
                    {
                        "title": title,
                        "due": None,
                        "evidence_id": "system",
                        "confidence": 0.0,
                        "source_ref": {"type": "system", "error": error_message},
                    }
                ],
            }
        ],
    )


def _sort_sections(sections: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_sections = []
    for section in sections:
        items = section.get("items", [])
        if not items:
            continue
        normalized_sections.append({"title": section.get("title", ""), "items": items})
    return sorted(
        normalized_sections,
        key=lambda section: (SECTION_ORDER.get(section["title"], 99), section["title"]),
    )


def _serialize_message(message: NormalizedMessage) -> Dict[str, Any]:
    payload = asdict(message)
    for key in ("datetime_received", "received_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return payload


def _deserialize_message(payload: Dict[str, Any]) -> NormalizedMessage:
    message_payload = dict(payload)
    for key in ("datetime_received", "received_at"):
        value = message_payload.get(key)
        if isinstance(value, str):
            message_payload[key] = datetime.fromisoformat(value)
    return NormalizedMessage(**message_payload)


def _dump_ingest_snapshot(
    path: Path, messages: Sequence[NormalizedMessage], digest_date: str
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "source": "ews",
            "digest_date": digest_date,
            "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
            "count": len(messages),
        },
        "messages": [_serialize_message(message) for message in messages],
    }
    _write_json(path, payload)


def _load_ingest_snapshot(path: Path) -> List[NormalizedMessage]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        messages = payload
    else:
        messages = payload.get("messages", [])
    return [_deserialize_message(message) for message in messages]


def _build_evidence_summary(
    *,
    threads: Sequence[Any],
    evidence_chunks: Sequence[EvidenceChunk],
    selected_evidence: Sequence[EvidenceChunk],
    selection_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    chunk_counts: Dict[str, int] = {}
    for chunk in evidence_chunks:
        chunk_counts[chunk.conversation_id] = (
            chunk_counts.get(chunk.conversation_id, 0) + 1
        )

    return {
        "chunk_count": len(evidence_chunks),
        "total_tokens": sum(chunk.token_count for chunk in evidence_chunks),
        "top_scores": [chunk.priority_score for chunk in list(evidence_chunks)[:5]],
        "filtered_service_count": 0,
        "selected_count": len(selected_evidence),
        "selection_metrics": selection_metrics,
        "per_thread": [
            {
                "conversation_id": thread.conversation_id,
                "message_count": getattr(
                    thread, "message_count", len(getattr(thread, "messages", []))
                ),
                "chunk_count": chunk_counts.get(thread.conversation_id, 0),
            }
            for thread in threads
        ],
    }


def _sanitize_config(config: Config) -> Dict[str, Any]:
    def sanitize(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {
                child_key: sanitize(child_value, child_key)
                for child_key, child_value in value.items()
            }
        if isinstance(value, list):
            return [sanitize(item, key) for item in value]
        if isinstance(value, str) and key.lower() in {
            "authorization",
            "token",
            "password",
            "secret",
        }:
            return "[[REDACTED]]"
        return value

    payload = config.model_dump(exclude_none=True)
    if payload.get("llm", {}).get("headers", {}).get("Authorization"):
        payload["llm"]["headers"]["Authorization"] = "[[REDACTED]]"
    return sanitize(payload)


def _record_stage_duration(
    run_meta: Dict[str, Any],
    metrics: MetricsCollector,
    stage: str,
    started_at: float,
) -> None:
    duration_seconds = time.perf_counter() - started_at
    run_meta["stage_durations_ms"][stage] = int(duration_seconds * 1000)
    metrics.record_pipeline_stage_duration(stage, duration_seconds)


def _count_digest_items(digest: Digest) -> int:
    return sum(len(section.items) for section in digest.sections)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
