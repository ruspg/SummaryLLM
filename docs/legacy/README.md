# Архивные документы

Этот каталог содержит документы, которые **больше не отражают актуальное состояние
проекта**, но сохраняются как исторические артефакты. Не используйте их как
руководство к действию.

## Что здесь и почему

| Файл | Дата архивации | Причина |
|------|---------------|---------|
| [`E2E_TESTING_GUIDE.md`](./E2E_TESTING_GUIDE.md) | 2026-04-06 | ~30% содержимого ссылается на shell-скрипты (`install_interactive.sh`, `doctor.sh`, `test_run.sh`), которые никогда не существовали в репозитории. |
| [`IMPLEMENTATION_SUMMARY.md`](./IMPLEMENTATION_SUMMARY.md) | 2026-04-06 | False-completion record: заявляет «✅ Создан и сделан исполняемым» о скриптах, которые в действительности не были созданы. |
| [`DOCUMENTATION_VALIDATION.md`](./DOCUMENTATION_VALIDATION.md) | 2026-04-06 | Мета-документ, описывающий валидацию несуществующих скриптов. |

## Где искать актуальную информацию

| Что вам нужно | Где смотреть |
|---------------|-------------|
| Установка и setup | [`README.md`](../../README.md) и [`digest-core/README.md`](../../digest-core/README.md). Канонический путь: `cd digest-core && make setup`. |
| Команды разработки | [`digest-core/CLAUDE.md`](../../digest-core/CLAUDE.md) — `make test`, `make smoke`, `make lint`. |
| Архитектура и контракты | [`digest-core/docs/ARCHITECTURE.md`](../../digest-core/docs/ARCHITECTURE.md) — single source of truth. |
| Диагностика окружения | `python -m digest_core.cli diagnose` |
| Сбор диагностического архива | `digest-core/scripts/collect_diagnostics.sh` |
| Ручное тестирование | [`docs/testing/MANUAL_TESTING_CHECKLIST.md`](../testing/MANUAL_TESTING_CHECKLIST.md) (актуализирован 2026-04-06) |
| Отправка результатов | [`docs/testing/SEND_RESULTS.md`](../testing/SEND_RESULTS.md) |
| Troubleshooting | [`docs/troubleshooting/TROUBLESHOOTING.md`](../troubleshooting/TROUBLESHOOTING.md) |

## Контекст

Документы выше были созданы в рамках раннего планирования Phase 0 (октябрь 2024)
и описывали инструментарий, который планировалось реализовать. Этот инструментарий
в итоге был заменён более простым подходом: интерактивный setup wizard
(`python -m digest_core.cli setup`, PR #32 / PR #33), `make`-цели для тестов и
smoke-тестирования, и `python -m digest_core.cli diagnose` для диагностики.

См. также: ACTPULSE-48 (консолидация процесс-доков), ACTPULSE-51 (Makefile vs
scripts/*.sh), ACTPULSE-60 (alignment setup-флоу).
