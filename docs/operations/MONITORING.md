# ActionPulse Monitoring Guide

Руководство по мониторингу и observability для ActionPulse. **Источник имён метрик и эндпоинтов:** `digest-core/src/digest_core/observability/metrics.py` и `healthz.py` (при расхождении с другими документами верьте коду).

## Metrics

### Prometheus endpoint

Метрики отдаются на **`http://<host>:9108/metrics`** (порт по умолчанию задаётся в конфиге `observability.prometheus_port`, см. `config.py`).

Ниже — основные семейства, реально объявленные в `MetricsCollector`:

| Метрика | Тип | Заметки |
|--------|-----|---------|
| `llm_latency_ms` | Histogram | Латентность LLM |
| `llm_tokens_in_total` | Counter | Входящие токены |
| `llm_tokens_out_total` | Counter | Исходящие токены |
| `llm_request_context_total` | Counter | Лейблы: `model`, `operation` (не `status`) |
| `emails_total` | Counter | Лейбл `status`: fetched, filtered, normalized, failed |
| `digest_build_seconds` | Summary | Время сборки дайджеста |
| `runs_total` | Counter | Лейбл `status`: ok, retry, failed |
| `evidence_chunks_total` | Counter | Лейбл `stage` |
| `threads_total` | Counter | Лейбл `status` |
| `pipeline_stage_duration_seconds` | Histogram | Лейбл `stage` (ingest, normalize, …) |
| `errors_total` | Counter | Лейблы `error_type`, `stage` |
| `memory_usage_bytes` | Gauge | Память процесса |
| `system_uptime_seconds` | Gauge | Аптайм |

Дополнительно в том же модуле объявлены счётчики/гистограммы для email cleaner, citations, actions, threading и др. Полный список — в исходнике `metrics.py`.

**Нет в коде (не используйте в алертах по старым гайдам):** отдельные `emails_processed_total` / `emails_failed_total`, `llm_requests_total{status}`, `digest_items_total`, `cpu_usage_percent`.

### Example queries

```promql
# Средняя латентность LLM (histogram)
rate(llm_latency_ms_sum[5m]) / rate(llm_latency_ms_count[5m])

# Успешные запуски за сутки
increase(runs_total{status="ok"}[24h])

# Письма с ошибкой нормализации/обработки (смотрите фактические значения label status)
rate(emails_total{status="failed"}[5m])
```

## Health checks

Поднимаются из `run.py`: метрики на порту **`config.observability.prometheus_port`** (по умолчанию **9108**), HTTP health — на **9109** (сейчас **зашит** в `run.py`, не отдельная ENV-переменная).

| Path | Порт | Назначение |
|------|------|------------|
| `/metrics` | 9108 | Prometheus scrape |
| `/healthz` | 9109 | Liveness: процесс жив |
| `/readyz` | 9109 | Readiness: проверка LLM gateway (если передан конфиг) |

### `/healthz` response

Минимальный JSON (см. `healthz.py`):

```json
{
  "status": "healthy",
  "service": "digest-core",
  "timestamp": 1710000000.123
}
```

`timestamp` — число с плавающей точкой (`time.time()`), не ISO-строка. Полей `version` и вложенных `checks` **нет**.

### `/readyz` response

Содержит `service`, `checks` (как минимум `llm_gateway` со статусом), общий `status` (`ready` / `not_ready`), `timestamp`. Отдельных проверок `ews_connectivity` или `disk_space` в коде **нет**.

Пример проверки:

```bash
curl -sf http://localhost:9109/healthz
curl -sf http://localhost:9109/readyz
```

## Logging

- Логи: **structlog**, JSON.
- Уровень задаётся флагом CLI **`--log-level`** при старте (`digest_core.cli run`), а не переменными `DIGEST_LOG_LEVEL` / `DIGEST_LOG_FORMAT` / `DIGEST_LOG_FILE` (они **не читаются** `logs.py`).
- В цепочке обработки событий используется процессор **`_redact_sensitive_data`** — часть полей маскируется **локально** в логах; тела писем по-прежнему не следует логировать вручную.

## Prometheus scrape config

```yaml
scrape_configs:
  - job_name: 'digest-core'
    static_configs:
      - targets: ['localhost:9108']
    scrape_interval: 30s
    metrics_path: /metrics
```

## Alerting (примеры)

```yaml
groups:
  - name: digest-core
    rules:
      - alert: DigestRunFailed
        expr: increase(runs_total{status="failed"}[1h]) > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Digest run failed"

      - alert: HighLLMLatency
        expr: rate(llm_latency_ms_sum[5m]) / rate(llm_latency_ms_count[5m]) > 30000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High LLM response time (check units: histogram is in ms)"
```

## Diagnostics

```bash
cd digest-core
make env-check
curl -s http://localhost:9108/metrics | head
```

Подробнее: `python -m digest_core.cli diagnose`, `export-diagnostics` — см. `digest-core/CLAUDE.md`.

## See Also

- [DEPLOYMENT.md](DEPLOYMENT.md)
- [AUTOMATION.md](AUTOMATION.md)
- [Troubleshooting](../troubleshooting/TROUBLESHOOTING.md)
