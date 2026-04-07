# Citation System: Extractive Traceability

> **Состояние на 2026-04-06:** при флаге **`--validate-citations`** пайплайн в `digest_core/run.py` после LLM **пересобирает** цитаты из **выбранных** evidence-чанков (`CitationBuilder`), **валидирует** смещения по нормализованному телу письма (`CitationValidator`), записывает результат в пункты v1-дайджеста и выставляет `run_meta.citation_validation_ok`. При провале CLI завершается с кодом **2** (артефакты при этом уже записаны). Каноничное описание: [`digest-core/docs/ARCHITECTURE.md` §8](../../digest-core/docs/ARCHITECTURE.md#8-error-taxonomy), пост-LLM шаги — перед §7 Assemble. Без флага пост-LLM citation pass **не** выполняется.

## Обзор

Система цитат (Citations) обеспечивает трассируемость каждого пункта дайджеста до исходного текста письма. Это extractive pipeline компонент, который:

- ✅ **Валидирует оффсеты**: каждая цитата имеет точные `start` и `end` оффсеты в нормализованном тексте
- ✅ **Гарантирует извлекаемость**: text[start:end] всегда возвращает корректный фрагмент
- ✅ **Поддерживает мультибайтные символы**: корректно работает с emoji, кириллицей, спецсимволами
- ✅ **Обеспечивает integrity**: SHA-256 checksums для верификации неизменности текста
- ✅ **Метрики и мониторинг**: Prometheus метрики для отслеживания качества

## Архитектура

### 1. Citation Model

```python
class Citation(BaseModel):
    msg_id: str          # Message ID reference
    start: int           # Start offset in normalized text (≥0)
    end: int             # End offset in normalized text (>start)
    preview: str         # Text preview text[start:end] (≤200 chars)
    checksum: str        # SHA-256 of normalized email body
```

**Важно**: Оффсеты считаются на тексте **ПОСЛЕ**:
1. HTML→text нормализации (`HTMLNormalizer.html_to_text()`)
2. Очистки (quote/signature removal via `QuoteCleaner.clean_email_body()`)

Это обеспечивает стабильность оффсетов и избежание ссылок на удаленный контент.

### 2. CitationBuilder

Строит `Citation` объекты из `EvidenceChunk`:

```python
builder = CitationBuilder(normalized_messages_map)
citation = builder.build_citation(chunk)
```

**Алгоритм**:
1. Извлекает `msg_id` из `chunk.source_ref`
2. Ищет `chunk.content` в `normalized_messages_map[msg_id]`
3. Если не найдено — применяет fuzzy matching (whitespace normalization)
4. Вычисляет `start`, `end` оффсеты
5. Создает preview (truncate до 200 chars)
6. Кэширует SHA-256 checksum нормализованного тела

### 3. CitationValidator

Валидирует citations перед записью в дайджест:

```python
validator = CitationValidator(normalized_messages_map)
is_valid = validator.validate_citations(citations, strict=False)
```

**Проверки**:
- ✅ `start >= 0`
- ✅ `end > start`
- ✅ `end <= len(normalized_body)`
- ✅ `text[start:end]` совпадает с `preview`
- ✅ Checksum совпадает (если указан)

**Режимы**:
- `strict=True`: останавливается на первой ошибке
- `strict=False`: собирает все ошибки в `validator.validation_errors`

## Интеграция в Pipeline

### Поведение `digest_core.cli run`

1. **Без `--validate-citations`:** после LLM собирается **`Digest`** и пишутся JSON/Markdown; цитаты в пунктах остаются теми, что пропустил gateway (если модель их вернула), без пост-LLM пересборки из чанков.
2. **С `--validate-citations`:** перед assemble выполняется пересборка и валидация цитат для всех пунктов с `evidence_id != "system"`. Пункты только со `system`, пустой дайджест и partial после сбоя LLM **не** требуют цитат (gate считается пройденным).
3. **Опционально `ranker.enabled`:** после шага цитат (если он был) или сразу после LLM — переупорядочивание пунктов по секциям (`DigestRanker`).

```
Ingest → … → LLM → [optional citations] → [optional ranker] → Assemble → Deliver
```

## CLI Usage

### Основной режим

```bash
cd digest-core
.venv/bin/python -m digest_core.cli run --from-date today
```

### Флаг `--validate-citations`

Включите для CI/гейта качества: при невозможности построить или провалидировать цитаты для обычных пунктов процесс завершится с **exit 2**. Смотрите также **`citation_validation_ok`** в `trace-*.meta.json`.

### Exit Codes (фактически)

- `0` — успех; при включённом флаге — и `citation_validation_ok` истинно
- `2` — провал citation validation при **`--validate-citations`**
- `1` — необработанное исключение / Typer error

## Метрики (Prometheus)

### citations_per_item_histogram

Гистограмма количества цитат на каждый пункт дайджеста.

**Buckets**: `[0, 1, 2, 3, 5, 10]`

**Использование**:
- Отслеживание среднего количества citations per item
- Выявление items без citations (bucket=0)

**Пример запроса**:
```promql
histogram_quantile(0.5, citations_per_item_histogram)  # медиана
sum(citations_per_item_histogram_bucket{le="0"})      # items без citations
```

### citation_validation_failures_total

Счетчик ошибок валидации citations.

**Labels**:
- `failure_type`: произвольная строка; при пост-LLM провале в `run.py` используется **`post_llm_offsets`** (см. `record_citation_validation_failure`). Другие типы возможны из будущих/прочих вызовов.

**Использование**:
- Мониторинг качества citation extraction
- Алерты при росте `offset_invalid` (может указывать на баги в normalize/cleaner)

**Пример запроса**:
```promql
rate(citation_validation_failures_total[5m])           # частота ошибок
sum by (failure_type) (citation_validation_failures_total)  # breakdown по типам
```

## Пример JSON Output

```json
{
  "schema_version": "2.0",
  "my_actions": [
    {
      "title": "Review PR #123",
      "description": "Code review required by Friday",
      "evidence_id": "ev-001",
      "quote": "Please review PR #123 by end of week",
      "citations": [
        {
          "msg_id": "msg-abc123",
          "start": 45,
          "end": 92,
          "preview": "Please review PR #123 by end of week. Thanks!",
          "checksum": "8f3e2a1b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f"
        }
      ],
      "confidence": "High"
    }
  ]
}
```

## Acceptance Criteria (DoD)

✅ **100% покрытие items**: каждый ActionItem, DeadlineMeeting, RiskBlocker, FYIItem, ThreadAction, ThreadDeadline имеет поле `citations: List[Citation]`

✅ **Валидация через CLI**: флаг `--validate-citations` подключён к пост-LLM проверке в `run.py` (см. блок в начале документа)

✅ **Метрики**: `citations_per_item_histogram`, `citation_validation_failures_total` записываются в Prometheus

✅ **Тесты**: 40+ тестов покрывают:
  - Успешное построение citations
  - Мультибайтные символы (emoji, русский текст, спецсимволы)
  - Негативные кейсы (invalid offsets, not found, checksum mismatch)
  - Edge cases (empty content, long text, whitespace differences)

✅ **Не ломает существующий pipeline**: citations — опциональное поле (default=[]), старый код работает без изменений

## Testing

### Запуск тестов

```bash
cd digest-core
pytest tests/test_citations.py -v

# С coverage
pytest tests/test_citations.py --cov=digest_core.evidence.citations --cov-report=term
```

### Тест-кейсы

#### Позитивные
- ✅ `test_build_citation_success`: базовый случай
- ✅ `test_build_citation_russian_text`: кириллица
- ✅ `test_build_citation_with_emoji`: multibyte chars
- ✅ `test_validate_valid_citation`: валидная цитата
- ✅ `test_enrich_action_item`: enrichment ActionItem

#### Негативные
- ❌ `test_build_citation_content_not_found`: контент не найден в письме
- ❌ `test_validate_invalid_start_offset`: start < 0
- ❌ `test_validate_invalid_end_offset`: end <= start
- ❌ `test_validate_offset_exceeds_length`: end > len(body)
- ❌ `test_validate_preview_mismatch`: preview не совпадает с text[start:end]
- ❌ `test_validate_checksum_mismatch`: SHA-256 не совпадает

#### Edge cases
- 🔸 `test_empty_content_chunk`: пустой chunk
- 🔸 `test_very_long_content`: 100KB+ письма
- 🔸 `test_whitespace_differences`: fuzzy matching пробелов

## Troubleshooting

### Проблема: Citation validation failed

**Симптомы**:
```
ERROR Citation validation failed errors=5
preview mismatch at offset 123:456
```

**Причины**:
1. Chunk content изменился между extraction и enrichment
2. Нормализатор изменил текст (whitespace, encoding)
3. Cleaner удалил часть текста, на которую ссылается chunk

**Решение**:
- Проверить логи cleaner: сколько chars removed
- Убедиться что chunks создаются **после** normalize+clean
- Проверить `normalized_messages_map` — корректные ли msg_id

### Проблема: Items без citations (bucket=0 в метриках)

**Симптомы**:
```promql
citations_per_item_histogram_bucket{le="0"} > 0
```

**Причины**:
1. `evidence_id` в item не совпадает с `evidence_id` в chunks
2. Chunk не найден в `evidence_chunks` list
3. Chunk.content не найден в normalized_body

**Решение**:
- Логировать `evidence_id` mapping в enrichment
- Проверить что LLM возвращает корректные `evidence_id`
- Включить DEBUG логи в `CitationBuilder`

### Проблема: Checksum mismatch

**Симптомы**:
```
ERROR Checksum mismatch for msg_id=msg-123
```

**Причины**:
1. Normalized body изменился между build и validate
2. Encoding issues (UTF-8 vs other)

**Решение**:
- Использовать immutable `normalized_messages_map`
- Проверить encoding в normalize stage

## Roadmap

### v1.0 (текущая реализация)
- ✅ Citation model в schemas
- ✅ CitationBuilder + CitationValidator
- ✅ Опциональная интеграция в pipeline (`run.py`, флаг `--validate-citations`)
- ✅ CLI exit **2** при провале валидации
- ✅ Prometheus метрики (`citation_validation_failures_total` и др.)
- ✅ Тесты (в т.ч. `test_e2e_pipeline.test_pipeline_validate_citations_replay`)

### v1.1 (планируется)
- 🔄 Multi-citation support: один item может ссылаться на несколько писем
- 🔄 Citation scoring: confidence/relevance для каждой цитаты
- 🔄 Citation deduplication: избежание дублирующих citations

### v2.0 (future)
- 🔜 Citation UI: визуализация citations в web-интерфейсе
- 🔜 Citation export: экспорт в аудит-форматы (PDF with highlights)
- 🔜 Citation feedback: пользовательская оценка quality citations

## References

- [Evidence Split Documentation](../src/digest_core/evidence/split.py)
- [QuoteCleaner Implementation](../src/digest_core/normalize/quotes.py)
- [Schemas v2](../src/digest_core/llm/schemas.py)
- [Prometheus Metrics](../src/digest_core/observability/metrics.py)

