# ActionPulse

**Daily pulse of actions from your inbox.**

Каждое утро — автоматический дайджест из корпоративной почты: что от тебя ждут, что срочно, что решили. Каждый пункт трассируется до оригинального письма.

---

## Что это

Single-tenant CLI инструмент. Читает Exchange inbox, прогоняет через 8-стадийный pipeline, доставляет в Mattermost DM.

**Не суммаризатор** — LLM извлекает факты из писем, а не пишет от себя. Три секции на выходе:
- **Мои действия** — что от тебя ожидают
- **Срочное** — дедлайны ≤2 рабочих дней
- **К сведению** — что решили без тебя

**Не SaaS** — работает на корп-инфраструктуре, данные не покидают периметр.

---

## Быстрый старт

```bash
git clone https://github.com/ruspg/ActionPulse.git
cd ActionPulse/digest-core

# Установка зависимостей + интерактивный мастер (6 вопросов, без редактирования файлов)
make setup

# Загрузить секреты в текущую сессию и проверить конфигурацию
set -a && source ~/.config/actionpulse/env && set +a
python -m digest_core.cli diagnose

# Dry-run (без LLM, только ingest + normalize)
python -m digest_core.cli run --dry-run

# Полный запуск
python -m digest_core.cli run
```

Мастер задаст: корпоративный email, EWS endpoint, EWS пароль, LLM endpoint, LLM токен, Mattermost webhook URL. Сгенерирует `~/.config/actionpulse/env` (chmod 600) и `configs/config.yaml`. Безопасно перезапускать: `python -m digest_core.cli setup`.

### Mattermost интеграция (важно)
ActionPulse использует **incoming webhook** Mattermost для **доставки** готового дайджеста (Stage 8). Для чтения сообщений/DM пассивно собирать данные не требуется — в MVP не используется API/WebSocket “для чтения”.

Подробнее — в [`digest-core/CLAUDE.md`](digest-core/CLAUDE.md).

---

## Архитектура

```
Exchange (EWS)
    └── INGEST → NORMALIZE → THREADS → EVIDENCE → SELECT → LLM → ASSEMBLE → DELIVER
                                                                               └── Mattermost DM
```

LLM: `qwen35-397b-a17b` через корп. gateway, 15 RPM, max 1 вызов за запуск.

Полные контракты стадий: [`digest-core/docs/ARCHITECTURE.md`](digest-core/docs/ARCHITECTURE.md).

---

## Принципы

| | |
|--|--|
| **Extract-over-Generate** | LLM извлекает из evidence, каждый пункт привязан к `evidence_id` |
| **Traceability** | Пункт → `evidence_id` → `source_ref` → оригинальное письмо |
| **Privacy-first** | PII маскируется на уровне LLM Gateway, локальное хранение ≤7 дней |
| **Idempotency** | `(user_id, date)` → один результат при любом числе перезапусков |

---

## Разработка

```bash
cd digest-core
make test    # все тесты (mocked, без сети)
make lint
make smoke   # dry-run smoke test
```

EWS и LLM Gateway — только с корп. сети. Для разработки вне периметра:

```bash
# Снять снапшот inbox'а изнутри
python -m digest_core.cli run --dump-ingest /tmp/snapshot.json

# Воспроизвести снаружи
python -m digest_core.cli run --replay-ingest /tmp/snapshot.json
```

---

## License

Internal corporate use only.
