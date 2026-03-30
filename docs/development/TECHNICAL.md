# (Технические детали, контракты, промпты, метрики)

## 1) Стек и рантайм

- **Python 3.11**, `typer` (CLI), `httpx` (HTTP), `exchangelib` (EWS), `pydantic(v2)`, `pydantic-settings`, `tenacity`, `structlog`, `prometheus-client`.
    
- Стиль: `ruff+black+isort`, частичная `mypy` на моделях.
    

## 2) Конфигурация (пример ключей)

```yaml
time:
  user_timezone: "Europe/Moscow"   # или America/New_York
  window: "calendar_day"           # options: rolling_24h | calendar_day

ews:
  endpoint: "https://<ews-host>/EWS/Exchange.asmx"
  user_upn: "user@corp"
  password_env: "EWS_PASSWORD"
  verify_ca: "/etc/ssl/corp-ca.pem"
  autodiscover: false
  folders: ["Inbox"]
  lookback_hours: 24
  page_size: 100
  sync_state_path: ".state/ews.syncstate"

llm:
  endpoint: "https://llm-gw.corp/api/v1/chat"
  model: "corp/qwen3.5-397b-a17b"
  timeout_s: 45
  headers:
    Authorization: "Bearer ${LLM_TOKEN}"
  max_tokens_per_run: 30000
  cost_limit_per_run: 5.0  # USD

observability:
  prometheus_port: 9108
  log_level: "INFO"
```

## 3) Нормализация писем (минимум)

- Поля: `msg_id`, `conversation_id`, `datetime_received` (UTC ISO), `sender.email`, `subject`, `text_body`.
    
- **Дедупликация**: `msg_id := InternetMessageId || EWSId (fallback)`, удалять угловые скобки, приводить к lower-case; `conversation_id` нормализовать к UTF-8 и фиксированной длине.
    
- **HTML→текст**: удаляем `<style>`, трекинги/подписи, корректно режем цитаты (`>`, `-----Original Message-----`, `От:`/`From:`).
    
- **Цитаты**: отсекать по маркерам `-----Original Message-----`, `From:`, `Переадресовано:`, `> ` (фьюз 5 уровней). Подписи: регулярки по `Best regards|С уважением`, `Sent from my iPhone`, блоки `DISCLAIMER`.
    
- **PII Policy**: Вся логика маскирования PII (email, телефоны, имена, SSN, кредитные карты, IP адреса) обрабатывается на стороне LLM Gateway API. Локально маскирование не выполняется.
    
- **Прикрепления**: Inline-attachments (`contentId` в `<img src="cid:...">`) игнорировать; binary attachments не загружать; общий лимит тела письма после очистки — 200 КБ (truncate с меткой `[TRUNCATED]`).
    

## 4) Схема JSON (контракт LLM)

```json
{
  "schema_version": "1.0",
  "prompt_version": "extract_actions.v1",
  "digest_date": "YYYY-MM-DD",
  "trace_id": "string",
  "sections": [
    {
      "title": "Мои действия",
      "items": [
        {
          "title": "string",
          "owners_masked": ["[[REDACT:...]]"],
          "due": "YYYY-MM-DD|null",
          "evidence_id": "string",
          "confidence": 0.0,
          "source_ref": {"type":"email","msg_id":"string","conversation_id":"string"}
        }
      ]
    }
  ]
}
```

- Валидация pydantic на каждом запуске. Любая нестыковка → ретрай LLM с жёсткой инструкцией.
    

## 5) EWS ошибки и ретраи

- **Retry**: 429/503 — jittered exponential backoff (base=0.5s, factor=2, max=60s), max_attempts=8; 5xx — max_attempts=5; 401/403 — без ретраев, немедленный фейл с меткой `auth_error`.

## 6) LLM Gateway — контракт запроса

- `POST {endpoint}` с `{model, messages:[{role:"system"/"user", content:"..."}]}`.
    
- Таймаут: 45s; ретрай 1–2 раза по `read/connect timeout`, 1 раз по «invalid JSON».
    
- **Ретраи по качеству**: если `items==0` и есть ≥1 evidence с позитивными сигналами — один ретрай с уточняющим system-сигналом. Если после ретрая невалидно — возвращать пустую секцию и логировать `llm_contract_violation=1`.
    
- **Лимиты**: совокупные токены на запуск ≤ 30 000; при превышении — агрессивная фильтрация низкоприоритетных тредов; метрика `llm_cost_estimate` (если доступна в Gateway).
    
- Логируем: `trace_id`, `status`, `latency_ms`, `tokens_in/out` (если возвращаются заголовками).
    

## 7) Промпты (версии и правила)

- Файлы `prompts/*.j2` (иммутабельны в рантайме; версионируем).
    
- **extract_actions.v1.j2** — извлекает только действия/срочность, сохраняет `[[REDACT:...]]`, отдаёт **строго JSON** по схеме (никакого текста вне JSON).
    
- **summarize.v1.j2** — собирает краткий Markdown ≤400 слов, каждый пункт с ссылкой на `evidence_id`.
    
- **Многоязычие**: если evidence на EN — оставлять исходный текст, заголовки секций — ru; не выполнять машинный перевод в MVP.

### Системные инварианты (вставляются в оба промпта)

- Всегда возвращай **строгий JSON** (или Markdown — когда это требуемый режим).
    
- Не раскрывай `[[REDACT:...]]`.
    
- Каждый айтем обязан иметь `evidence_id` и `source_ref`.
    
- Russian locale по умолчанию; даты в ISO.
    

## 8) Селектор контекста (эвристики)

- **Положительные сигналы**: imperative глаголы, дедлайны (`до|by|ДД.ММ|YYYY-MM-DD`), обращения к адресату (вы/you + имя).
    
- **Отрицательные сигналы**: `FYI`, `newsletter`, `digest`.
    
- **Ранжирование**: приоритет письм To-адресату > CC.
    
- **Фильтрация служебных писем**: Out-of-Office, Delivery Status Notification, spam-notices; признак — заголовки `Auto-Submitted`, темы `[Автоответ]`, `Undeliverable`, отправитель `postmaster@` и т. п.

## 9) Идемпотентность и high-water mark

- `(user_id, digest_date)` — ключ.
    
- Окно перестроения **T-48ч**: если входные данные менялись — пересобрать.
    
- EWS watermark как ISO timestamp в локальном `.state/ews.syncstate` для инкрементальной выборки. В MVP без `SyncFolderItems` - fallback на полный интервал при повреждении состояния.
    

## 10) Наблюдаемость (Prometheus + логи)

- **Метрики**:
    
    - `llm_latency_ms` (histogram), `llm_tokens_in_total`, `llm_tokens_out_total`,
        
    - `digest_build_seconds` (summary),
        
    - `emails_total{status="fetched|filtered"}`,
        
    - `runs_total{status="ok|retry|failed"}`.
        
- **Кардинальность**: лимитируем лейблы до: `status`, `source`, `stage`. Без `msg_id` в метриках. Экспонируем `/healthz` (liveness) и `/readyz` (readiness).
        
- **Логи**: structlog JSON (`run_id`, `trace_id`, стадия пайплайна, счётчики); **без** тел писем/секретов.
    
- **Redaction**: все строки проходят redaction-фильтр (email/телефон/ID→`[[REDACT:...]]`). Уровни: `INFO` — этапы пайплайна; `WARN` — деградации качества/обрезки; `ERROR` — фатальные; ни при каком уровне не логировать тело писем.
    

## 11) CLI и конфигурация

- **Флаги**: `--from_date`, `--sources`, `--out`, `--model`, `--window`, `--dry-run` (без вызова LLM, только ingest+normalize+stats).
    
- **Коды возврата**: 0 — OK, 2 — частичный успех, 1 — ошибка.

## 12) Тесты/снапшоты

- `tests/test_llm_contract.py` валидирует образец `examples/digest-YYYY-MM-DD.json`.
    
- **Фикстуры**: `tests/fixtures/` с 30+ писем (html/txt), в т. ч. автоответы, NDR, длинные треды, кириллица/latin-1, вложенные цитаты. Покрытие unit-тестами ≥70% модулей normalize/select/masking.
    
- Снапшоты Markdown/JSON — фиксируем регрессию; для не-детерминизма — стабилизируем селекцию (правила + сортировки).
    
