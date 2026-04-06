# Key Performance Indicators (KPI)

> ## ⚠️ Status: Целевые KPI — большая часть пока не инструментирована
>
> Этот документ описывает **целевые** KPI, которые мы хотим отслеживать. Часть из
> них требует gold-set evaluation и/или дополнительной инструментации, которой
> сегодня в коде нет.
>
> **Что инструментировано сегодня** (см.
> [`metrics.py`](../../digest-core/src/digest_core/observability/metrics.py) и
> [`ARCHITECTURE.md §6.1`](../../digest-core/docs/ARCHITECTURE.md)):
>
> - Производительность / latency: `digest_build_seconds`, `pipeline_stage_duration_seconds`,
>   `llm_latency_ms`, `runs_total{status}`
> - Объёмы: `emails_total{status}`, `evidence_chunks_total{stage}`, `threads_total{status}`,
>   `llm_tokens_in_total`, `llm_tokens_out_total`
> - Качество (counters, не P/R/F1): `actions_found_total{action_type}`,
>   `mentions_found_total`, `actions_confidence_histogram`, `citations_per_item_histogram`
> - Ошибки и деградации: `errors_total{error_type,stage}`, `degradations_total{reason}`,
>   `validation_error_total{type}`, `llm_json_error_total`, `citation_validation_failures_total`
> - Прочее: `redundancy_index`, `top10_actions_share`, `rank_score_histogram`
>
> **Что НЕ инструментировано** (целевые KPI ниже, помеченные 🔴):
>
> - 🔴 `coverage_significant_events` — требует gold-set
> - 🔴 `action_items_accuracy` (P/R/F1, exact-match) — требует gold-set + аннотации
> - 🔴 `digest_generation_time_p90` — есть `digest_build_seconds` Summary, но не отдельный p90 gauge
> - 🔴 `bot_delivery_sla` — нет отслеживания окна доставки
> - 🔴 `user_satisfaction_score` — нет фидбек-механизма (👍/👎 в MM bot — Phase 1+)
> - 🔴 `mentions_f1` / `mentions_precision` / `mentions_recall` / Brier Score — требуют gold-set
> - 🔴 `hallucination_rate` — требует валидации против evidence outside `validate_citations`
>
> Документ ведётся как target spec; раздел "Status" обновляется по мере
> реализации соответствующих метрик.

Ключевые показатели эффективности и целевые метрики для ActionPulse.

## Основные KPI

### Покрытие значимых писем/сообщений

- **Цель:** ≥ 90%
- **Как считаем:** По gold-сету значимых событий
- **Метрика:** `coverage_significant_events`
- **Формула:** `(количество_найденных_значимых / общее_количество_значимых) * 100`

### Точность Action Items

- **Цель:** ≥ 80%
- **Как считаем:** Exact-match по (тип действия, владелец, срок) + F1
- **Метрика:** `action_items_accuracy`
- **Компоненты:**
  - Precision: `true_positives / (true_positives + false_positives)`
  - Recall: `true_positives / (true_positives + false_negatives)`
  - F1: `2 * (precision * recall) / (precision + recall)`

### Время генерации (T90)

- **Цель:** ≤ 60 сек (MVP–LVL2), ≤ 90 сек (LVL3–4)
- **Как считаем:** По стадиям: ingest / LLM / assemble
- **Метрика:** `digest_generation_time_p90`
- **Компоненты:**
  - EWS ingest time
  - Normalization time
  - LLM processing time
  - Assembly time

### SLA доставки бота

- **Цель:** ≥ 95%
- **Как считаем:** Доля доставок в окно ±5 мин
- **Метрика:** `bot_delivery_sla`
- **Формула:** `(успешные_доставки_в_окно / общее_количество_попыток) * 100`

### Пользовательская оценка пользы

- **Цель:** ≥ 4/5
- **Как считаем:** Опрос в боте + доля скрытых «noise»
- **Метрика:** `user_satisfaction_score`
- **Компоненты:**
  - Рейтинг полезности (1-5)
  - Доля скрытых нерелевантных элементов
  - Частота использования

## Детальные метрики качества

### Mentions Detection

- **Precision:** ≥ 0.85
- **Recall:** ≥ 0.80
- **F1 Score:** ≥ 0.82
- **Brier Score:** ≤ 0.15 (калибровка)
- **Citation Accuracy:** ≥ 90% (корректные цитаты)

### Action Items Extraction

- **Exact Match:** ≥ 80% (тип/владелец/срок)
- **Partial Match:** ≥ 90% (тип + владелец)
- **False Positive Rate:** ≤ 15%
- **Coverage:** ≥ 85% значимых действий

### Citation Fidelity

- **Valid Links:** ≥ 95% пунктов с валидной ссылкой
- **Correct Spans:** ≥ 90% корректных evidence spans
- **Hallucination Rate:** ≤ 5% пунктов без evidence

## Технические метрики

### Производительность

| Метрика | Цель | Единица |
|---------|------|---------|
| EWS Connection Time | ≤ 5 сек | секунды |
| LLM Response Time (P95) | ≤ 30 сек | секунды |
| Memory Usage | ≤ 512 MB | мегабайты |
| CPU Usage (avg) | ≤ 50% | проценты |

### Надёжность

| Метрика | Цель | Единица |
|---------|------|---------|
| Success Rate | ≥ 99% | проценты |
| Error Rate | ≤ 1% | проценты |
| Retry Success Rate | ≥ 80% | проценты |
| Data Loss Rate | 0% | проценты |

### Стоимость

| Метрика | Цель | Единица |
|---------|------|---------|
| Cost per Digest | ≤ $0.10 | USD |
| Tokens per Run | ≤ 30,000 | токены |
| Cache Hit Rate | ≥ 70% | проценты |
| Cost per User per Month | ≤ $5.00 | USD |

## Метрики приватности и безопасности

### PII Handling

- **PII Detection Rate:** ≥ 99%
- **PII Masking Accuracy:** ≥ 99.9%
- **PII Leakage Rate:** 0% (критично)
- **Consent Compliance:** 100%

### Аудит и соответствие

- **Audit Log Coverage:** 100%
- **Data Retention Compliance:** 100%
- **Access Control Violations:** 0
- **Security Incident Rate:** 0

## Метрики пользовательского опыта

### Удобство использования

- **Daily Active Users:** рост на 10% в месяц
- **User Retention (30 days):** ≥ 80%
- **Feature Adoption Rate:** ≥ 60%
- **Support Ticket Rate:** ≤ 5% пользователей в месяц

### Качество контента

- **Relevance Score:** ≥ 4.0/5.0
- **Noise Reduction:** ≥ 70%
- **Action Completion Rate:** ≥ 60%
- **Time to Action:** ≤ 2 минуты

## Мониторинг и алерты

### Критические алерты

- **SLA доставки < 90%** - немедленное уведомление
- **PII утечка** - критический инцидент
- **Время генерации > 120 сек** - предупреждение
- **Ошибки > 5%** - предупреждение

### Предупреждающие алерты

- **SLA доставки < 95%** - уведомление
- **Пользовательская оценка < 3.5** - анализ
- **Стоимость > $0.15 за дайджест** - оптимизация
- **Cache hit rate < 50%** - анализ

## Отчётность

### Ежедневные отчёты

- Количество обработанных дайджестов
- Время генерации (среднее, P95)
- Количество ошибок
- Стоимость использования

### Еженедельные отчёты

- Пользовательская активность
- Качество извлечения (P/R/F1)
- Тренды производительности
- Проблемы и инциденты

### Ежемесячные отчёты

- Общие KPI и тренды
- Пользовательская удовлетворённость
- Стоимость и ROI
- Планы улучшения

## Целевые значения по этапам

### MVP (Текущий)

- Покрытие: ≥ 85%
- Точность действий: ≥ 75%
- Время генерации: ≤ 60 сек
- Пользовательская оценка: ≥ 3.5/5

### LVL2 (Mentions)

- Покрытие: ≥ 90%
- Точность действий: ≥ 80%
- Mentions P/R: ≥ 0.85/0.80
- Время генерации: ≤ 60 сек

### LVL3 (Mattermost)

- Покрытие: ≥ 90%
- Точность действий: ≥ 80%
- Время генерации: ≤ 90 сек
- SLA доставки: ≥ 95%

### LVL4 (DM)

- Все метрики LVL3
- PII утечки: 0%
- Consent compliance: 100%

### LVL5 (Bot)

- Все метрики LVL4
- Bot SLA: ≥ 95%
- Response time: ≤ 5 сек
- User satisfaction: ≥ 4.0/5

## Инструменты мониторинга

### Prometheus метрики

```promql
# Основные KPI
coverage_significant_events
action_items_accuracy
digest_generation_time_p90
bot_delivery_sla
user_satisfaction_score

# Технические метрики
ews_connection_time_seconds
llm_response_time_seconds
memory_usage_bytes
cpu_usage_percent

# Метрики качества
mentions_precision
mentions_recall
citation_fidelity
hallucination_rate
```

### Grafana дашборды

- **Executive Dashboard** - основные KPI для руководства
- **Technical Dashboard** - технические метрики для разработчиков
- **Quality Dashboard** - метрики качества для ML команды
- **User Experience Dashboard** - пользовательские метрики

### Алерты

- **PagerDuty** - критические инциденты
- **Slack** - предупреждения и уведомления
- **Email** - еженедельные отчёты

---

**Итог:** Эти KPI обеспечивают комплексный мониторинг эффективности ActionPulse на всех уровнях - от технических метрик до пользовательского опыта и бизнес-ценности.
