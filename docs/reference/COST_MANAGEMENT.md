# Cost Management and Budget Control

> ## Статус документа (сверка с кодом, 2026-04)
>
> Этот файл разделяет **фактическое поведение MVP (Phase 0)** и **целевой дизайн Phase 1+**.
> Каноничные контракты и лимиты: [`digest-core/docs/ARCHITECTURE.md`](../../digest-core/docs/ARCHITECTURE.md)
> (§2 принципы, §4 стадии, §5 конфиг, §6.1 метрики, §13.2 TD-006).

## Что реализовано сегодня (Phase 0)

### Лимиты объёма контекста (до LLM)

- **`context_budget.max_total_tokens`** (по умолчанию **7000**) ограничивает суммарный heuristic `token_count` evidence на **Stage 4** и участвует в отборе на **Stage 5** (`ContextSelector`, бакеты, опциональный shrink). См. ARCHITECTURE §4.2–4.2.1, `config.py` / YAML `context_budget`, ENV `DIGEST_CTX_BUDGET_*`.
- **`chunking.*`** (`max_tokens_per_chunk`, и т.д.) задаёт разбиение чанков, не «стоимость в USD».

### Лимиты числа и частоты LLM-вызовов

- **Не более 2 логических вызовов** на прогон (primary + optional quality retry), см. **ADR-008** и ARCHITECTURE §4.2.1 Stage 6.
- **Ограничение шлюза: 15 RPM** — учитывается при проектировании пайплайна; в коде есть интервал между запросами (`MIN_LLM_INTERVAL_SECONDS` в `llm/gateway.py`).
- Параметр запроса **`max_tokens`: 2000** для completion — см. `_make_request_once` в `gateway.py` (не путать с `max_tokens_per_run`).

### Лимит токенов на прогон (run-level)

- **`LLMConfig.max_tokens_per_run`** (по умолчанию **30 000**): после каждого успешно разобранного ответа шлюз накапливает `tokens_in + tokens_out` и при превышении порога выбрасывает **`TokenBudgetExceeded`** (`llm/gateway.py`, проверка после обновления `_run_tokens_used`).
- Это **не** ценообразование в USD и **не** биллинг — только защита от неконтролируемого роста токенов за один запуск (включая quality retry).

### Поле конфига без enforcement

- **`llm.cost_limit_per_run`** (USD, placeholder в YAML §5.1 ARCHITECTURE) **нигде не проверяется** в коде. Открытый техдолг: **TD-006** в ARCHITECTURE §13.2.

### Деградация при сбоях (не «экономия», но снижение риска)

- Сбой LLM после ретраев → **partial digest** (секция «Статус»), см. P5 / ADR в ARCHITECTURE.
- Отдельных стратегий «выкрутить USD» в рантайме **нет**.

### Prometheus (факт)

- Счётчики **`llm_tokens_in_total`**, **`llm_tokens_out_total`** и latency/run-метрики — см. `observability/metrics.py`, ARCHITECTURE §6.1.
- Метрик вида **`llm_cost_usd_total`**, **`cost_per_digest_usd`**, **`budget_utilization_percent`** в коде **нет**; оценка денег — вне репозитория (тариф gateway / FinOps).

---

## Оценка стоимости в эксплуатации (вне кода)

Для MVP оператор обычно:

1. Снимает **`llm_tokens_in_total` / `llm_tokens_out_total`** (или поля `tokens_in` / `tokens_out` в `trace-*.meta.json` / логах) за период.
2. Умножает на **цену за 1K токенов** по договору с corp LLM Gateway.
3. Сопоставляет с **`max_tokens_per_run`** и частотой cron (1 run / user / day).

Пер-user / per-org **лимиты в USD** в продукте **не реализованы** (Phase 1+).

---

## Phase 1+ (целевое состояние — не реализовано)

Ниже — направления развития, **без** привязки к текущему коду.

### Планируемые возможности

- **Enforcement `cost_limit_per_run`** и/или квоты per-user / per-org (TD-006 и смежные задачи).
- **CostOptimizer**-подобная логика: автоматическое сжатие контекста, отключение дорогих путей — только после отдельного ADR (сейчас контроль — `context_budget`, selection, partial digest).
- **Prometheus**: явные метрики стоимости в USD только если появится надёжный источник цены и политика разметки по `model`.
- **Отчёты и алерты** по бюджету в USD — поверх внешней биллинг-системы или кастомных правил в Grafana.

### Иллюстративные YAML (не в `config.py` сегодня)

```yaml
# НЕ подключено к Pydantic Config — пример для Phase 1+
cost_limits:
  per_user:
    daily_usd: 0.50
  per_digest:
    max_usd: 0.10
```

---

## Связь с другими документами

| Тема | Где читать |
|------|------------|
| Лимиты токенов evidence / chunking | ARCHITECTURE §4.2, §5.1 `context_budget`, `chunking` |
| LLM вызовы, RPM, retry | ARCHITECTURE §4.2.1 Stage 6, ADR-008 |
| Конфиг LLM | ARCHITECTURE §5.1 `llm:` |
| Метрики | ARCHITECTURE §6.1, `metrics.py` |
| Техдолг cost USD | ARCHITECTURE §13.2 **TD-006** |
| KPI и покрытие метрик | [`KPI.md`](./KPI.md) |

---

**Итог (Phase 0):** стоимость держится в рамках за счёт **ограничения контекста**, **малого числа LLM-вызовов**, **RPM-дисциплины** и опционального **`max_tokens_per_run`**. Денежные лимиты и «cost optimizer» в продукте **отсутствуют**; `cost_limit_per_run` — заготовка под TD-006.
