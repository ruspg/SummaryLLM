# Quick Start Guide

Быстрый старт с ActionPulse - получите первый дайджест за 5 минут.

## Автоматическая установка (рекомендуется)

### Одна команда для полной установки

```bash
# Полная установка с интерактивной настройкой
curl -fsSL https://raw.githubusercontent.com/ruspg/ActionPulse/main/digest-core/scripts/install.sh | bash

# Или: без интерактивной настройки (только клонирование + зависимости)
curl -fsSL https://raw.githubusercontent.com/ruspg/ActionPulse/main/digest-core/scripts/install.sh | bash -s -- --skip-setup
```

### Что происходит при установке

1. **Клонирование репозитория** в `~/ActionPulse`
2. **Проверка зависимостей** (Python 3.11+, uv, docker)
3. **Установка зависимостей** (если нужно)
4. **Интерактивная настройка** (только для полной установки)
5. **Создание конфигурационных файлов**

## Ручная установка

### Если у вас уже есть клон репозитория

```bash
# Запуск интерактивного мастера настройки
./digest-core/scripts/setup.sh

# Или из директории digest-core
cd digest-core && make setup-wizard
```

## Первый запуск

### 1. Активируйте окружение

```bash
cd ~/ActionPulse
set -a && source .env && set +a
```

### 2. Перейдите в директорию digest-core

```bash
cd digest-core
```

### 3. Установите зависимости (если не сделали в setup)

```bash
make setup
```

### 4. Проверьте конфигурацию

```bash
make env-check
```

### 5. Запустите первый дайджест

> **Требуется Python 3.11+**. На macOS установите `brew install python@3.11` и используйте `python3.11` явно.

```bash
# Тестовый запуск (без LLM) - проверяет только EWS подключение
python3.11 -m digest_core.cli run --dry-run

# Полный запуск для сегодня
python3.11 -m digest_core.cli run
```

## Основные команды

```bash
# Базовый запуск (дайджест за сегодня)
python3.11 -m digest_core.cli run

# Для конкретной даты
python3.11 -m digest_core.cli run --from-date 2024-01-15

# Dry-run режим (только ingest+normalize, без LLM)
python3.11 -m digest_core.cli run --dry-run

# Другая модель LLM
python3.11 -m digest_core.cli run --model "qwen35-397b-a17b"

# Кастомная директория вывода
python3.11 -m digest_core.cli run --out ./my-digests

# Используя make
make run
```

## Просмотр результатов

После успешного запуска в директории `digest-core/out/` будут созданы файлы:

- `digest-YYYY-MM-DD.json` - структурированные данные с полной схемой
- `digest-YYYY-MM-DD.md` - человеко-читаемый дайджест (≤400 слов)

### Пример просмотра результатов

```bash
# Посмотреть JSON структуру
cat digest-core/out/digest-2024-01-15.json | jq '.'

# Посмотреть Markdown дайджест
cat digest-core/out/digest-2024-01-15.md

# Найти все дайджесты
ls -la digest-core/out/digest-*.md
```

## Структура выходных файлов

- Каждый элемент содержит `evidence_id` для ссылки на источник
- `source_ref` указывает на исходное сообщение
- `confidence` показывает уверенность в извлечении (0-1)
- `owners_masked` содержит замаскированные имена ответственных

## Автоматизация

### Настройка cron для ежедневного запуска

```bash
# Добавить в crontab (запуск каждый день в 8:00)
crontab -e

# Добавить строку:
0 8 * * * cd /path/to/ActionPulse/digest-core && set -a && source ../.env && set +a && .venv/bin/python -m digest_core.cli run
```

### Использование systemd (Linux)

Для детальных инструкций по настройке systemd таймера см. [DEPLOYMENT.md](../operations/DEPLOYMENT.md#scheduling).

## Мониторинг и отладка

```bash
# Проверить метрики Prometheus
curl http://localhost:9108/metrics

# Проверить health check
curl http://localhost:9109/healthz

# Посмотреть логи (если запущено в Docker)
docker logs digest-core-container

# Проверить конфигурацию
cd digest-core && make env-check
```

## Что дальше?

### Изучите документацию

- 📚 [Полная документация](../README.md)
- 🔧 [Детальное руководство по установке](INSTALL.md)
- 🐳 [Развертывание в продакшене](../operations/DEPLOYMENT.md)
- 📊 [Мониторинг и observability](../operations/MONITORING.md)
- 🚨 [Решение проблем](../troubleshooting/TROUBLESHOOTING.md)

### Настройте автоматизацию

- ⏰ [Настройка автоматизации](../operations/AUTOMATION.md)
- 🔄 [Управление состоянием и ротация](../operations/AUTOMATION.md#state-management)
- 📈 [Мониторинг производительности](../operations/MONITORING.md)

### Расширьте функциональность

- 🗺️ [Roadmap развития](../planning/ROADMAP.md)
- 🤖 [Интеграция с Mattermost](../planning/MATTERMOST_INTEGRATION.md)
- 📊 [Метрики качества](../reference/QUALITY_METRICS.md)

## Получение помощи

### Если что-то не работает

1. **Проверьте [TROUBLESHOOTING.md](../troubleshooting/TROUBLESHOOTING.md)**
2. **Запустите диагностику:**
   ```bash
   cd digest-core && make env-check
   ```
3. **Проверьте логи:**
   ```bash
   python -m digest_core.cli run --verbose
   ```

### Создание issue

При создании issue включите:
- Вывод `make env-check`
- Соответствующие логи
- Конфигурацию (без секретов)
- Шаги для воспроизведения

---

**Поздравляем!** 🎉 Вы успешно запустили ActionPulse. Теперь у вас есть автоматический дайджест корпоративных коммуникаций!
