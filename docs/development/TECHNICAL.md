# Технические детали ActionPulse

> **Этот файл — редирект.** Единственный источник правды (SoT) для технических
> деталей `digest-core` находится здесь:
>
> 📖 **[`digest-core/docs/ARCHITECTURE.md`](../../digest-core/docs/ARCHITECTURE.md)**

Файл `docs/development/TECHNICAL.md` (этот файл) ранее содержал высокоуровневую
техническую сводку (стек, конфиг, контракты, промпты, метрики), которая
расходилась с реальным кодом и основным SoT-документом по нескольким параметрам
(`timeout_s`, формат промптов, exit codes, список Prometheus метрик). Чтобы
избежать дальнейшего рассинхрона, содержимое заменено на этот указатель.

Все архитектурные решения, контракты стадий, ADR, схема JSON, метрики и
известный технический долг ведутся в `digest-core/docs/ARCHITECTURE.md`.

---

## Куда смотреть для конкретной задачи

| Что | Где |
|-----|-----|
| Архитектура, ADR, контракты стадий, схема JSON | [`digest-core/docs/ARCHITECTURE.md`](../../digest-core/docs/ARCHITECTURE.md) |
| Команды разработки, gotchas, exit codes | [`digest-core/CLAUDE.md`](../../digest-core/CLAUDE.md) |
| Развёртывание (Docker, systemd, cron) | [`digest-core/docs/DEPLOYMENT.md`](../../digest-core/docs/DEPLOYMENT.md) |
| Установка и setup | Корневой [`README.md`](../../README.md) и [`digest-core/README.md`](../../digest-core/README.md) |
| Бизнес-требования | [`docs/planning/BUSINESS_REQUIREMENTS.md`](../planning/BUSINESS_REQUIREMENTS.md) |
| Roadmap | [`docs/planning/ROADMAP.md`](../planning/ROADMAP.md) |
| Troubleshooting | [`docs/troubleshooting/TROUBLESHOOTING.md`](../troubleshooting/TROUBLESHOOTING.md) |
| Стратегия тестов | [`docs/development/TESTING.md`](./TESTING.md) |
