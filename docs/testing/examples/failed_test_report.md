# Пример отчета о тестировании с проблемами

> **📌 Примечание (2026-04-06):** Этот пример был написан для раннего варианта
> setup-инструментария и упоминает скрипты `install_interactive.sh`, `doctor.sh`,
> которые в действительности **никогда не существовали в репозитории**. Шаблон
> остаётся полезным как образец описания проблем, но при копировании заменяйте:
> - `install_interactive.sh` → `make setup` (см. корневой [`README.md`](../../../README.md))
> - `doctor.sh` → `python -m digest_core.cli diagnose`
> - `test_run.sh` → `python -m digest_core.cli run`
> - `collect_diagnostics.sh` остаётся как есть (это реальный скрипт)

## Email шаблон

**Тема:** `ActionPulse Test Results - 2024-10-13 - ISSUES FOUND`

**Тело письма:**

```
Здравствуйте!

Провел end-to-end тестирование ActionPulse на корпоративном ноутбуке Windows с WSL.

=== РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ===

✓ Установка: Успешно (ручная установка)
⚠ Конфигурация: С предупреждениями
✓ Smoke-тесты (dry-run): Успешно
✗ Полный цикл: Неуспешно (см. проблемы ниже)
✓ Сбор диагностики: Успешно

=== МЕТРИКИ ===

- Время выполнения полного цикла: Не завершился (timeout после 15 минут)
- Обработано писем: 152 (получено, но не обработано LLM)
- Создано секций в дайджесте: 0 (не создан из-за ошибки)

=== НАЙДЕННЫЕ ПРОБЛЕМЫ ===

1. **SSL Certificate Verification Failed**
   - Ошибка: `SSLCertVerificationError: certificate verify failed`
   - Файл: src/digest_core/ingest/ews.py, line 85
   - Контекст: При подключении к EWS endpoint
   - Workaround: Временно установил `verify_ssl: false` в config.yaml
   - Статус: Тест продолжен, но требуется решение для production
   - Stack trace: См. архив диагностики, logs/run-*.log

2. **LLM Gateway Timeout**
   - Ошибка: `ConnectionTimeout: Request timeout after 300s`
   - Файл: src/digest_core/llm/gateway.py, line 142
   - Контекст: При вызове LLM для извлечения действий
   - Возможная причина: Большой объем данных (152 письма) или медленный LLM endpoint
   - Статус: Не решено
   - Рекомендация: Добавить pagination или увеличить timeout

3. **Permission Denied при записи в /tmp**
   - Ошибка: `PermissionError: [Errno 13] Permission denied: '/tmp/diagnostics'`
   - Файл: digest-core/scripts/collect_diagnostics.sh, line 23
   - Контекст: При сборе диагностики
   - Workaround: Использовал `export TMPDIR=$HOME/.digest-temp`
   - Статус: Решено через workaround
   - Примечание: Типично для корпоративных Windows машин

=== СИСТЕМНАЯ ИНФОРМАЦИЯ ===

- ОС: Windows 11 Pro (Build 22621) + WSL2 (Ubuntu 22.04)
- Python: 3.11.4
- Git: 2.39.2
- Доступ к Exchange: OK (с предупреждением о SSL)
- Доступ к LLM Gateway: Timeout
- Виртуальное окружение: digest-core/.venv (активно)
- Корпоративный прокси: Да (http://proxy.company.com:8080)

=== РЕКОМЕНДАЦИИ ===

1. **Добавить поддержку корпоративных CA сертификатов**
   - Документировать процесс установки корп. сертификатов в trust store
   - Добавить опцию `verify_ca` в config.yaml для указания пути к CA bundle
   - Возможно, включить в install_interactive.sh проверку на корп. сертификаты

2. **Оптимизировать работу с большими объемами писем**
   - Увеличить default timeout для LLM запросов с 300s до 600s
   - Добавить pagination: обрабатывать письма батчами по 50
   - Добавить progress bar для длительных операций

3. **Улучшить поддержку Windows/WSL**
   - Документировать особенности WSL в E2E_TESTING_GUIDE.md
   - Автоматически определять WSL и использовать $HOME вместо /tmp
   - Добавить в doctor.sh проверку на WSL

4. **Добавить retry logic**
   - Для LLM запросов: retry 3 раза с exponential backoff
   - Для EWS подключений: retry при временных network errors

=== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ===

Вывод doctor.sh перед запуском:
```
✓ Python 3.11.4 найден
✓ Git 2.39.2 найден
✓ Виртуальное окружение найдено
⚠ CA сертификат не указан в config.yaml
✓ OUT_DIR доступна для записи
⚠ Нет доступа к LLM Gateway (проверьте позже)
```

Прикреплен архив диагностики: diagnostics-2024-10-13-16-45-10.tar.gz (размер: 2.8 MB)
Включает полные логи всех ошибок и stack traces.

С уважением,
Мария Тестова
```

**Прикрепленные файлы:**
- `diagnostics-2024-10-13-16-45-10.tar.gz` (2.8 MB)

---

## Характеристики отчета с проблемами

### Что обязательно включить

1. **Детальное описание каждой проблемы:**
   - ✅ Точное сообщение об ошибке
   - ✅ Файл и номер строки (если известно)
   - ✅ Контекст возникновения
   - ✅ Примененные workarounds
   - ✅ Статус (решено/не решено)

2. **Stack traces:**
   - Включить в архив диагностики
   - Упомянуть в отчете, где найти

3. **Попытки решения:**
   - Что вы пробовали
   - Что сработало, что нет
   - Ссылки на документацию, которую использовали

4. **Рекомендации по исправлению:**
   - Конкретные предложения для разработчиков
   - Приоритизация (critical/high/medium/low)

### Формат описания проблемы

```
N. **Краткое название проблемы**
   - Ошибка: `Точное сообщение об ошибке`
   - Файл: путь/к/файлу.py, line XX
   - Контекст: Когда возникает
   - Workaround: Что сделали для обхода (если есть)
   - Статус: Решено/Не решено/Частично решено
   - Рекомендация: Как исправить
   - Приоритет: Critical/High/Medium/Low
```

---

## Типичные проблемы на корпоративных ноутбуках

### 1. SSL/TLS сертификаты

**Проблема:**
```
SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self signed certificate in certificate chain
```

**Возможные причины:**
- Корпоративный CA не в trust store
- MITM прокси с самоподписанным сертификатом
- Expired корпоративный сертификат

**Workarounds:**
```yaml
# В config.yaml (временно):
ews:
  verify_ssl: false

# Правильное решение:
ews:
  verify_ca: "/path/to/corporate-ca-bundle.pem"
  verify_ssl: true
```

### 2. Проблемы с правами доступа

**Проблема:**
```
PermissionError: [Errno 13] Permission denied: '/tmp/...'
```

**Workaround:**
```bash
export OUT_DIR="$HOME/.digest-out"
export STATE_DIR="$HOME/.digest-state"
export TMPDIR="$HOME/.digest-temp"
```

### 3. Proxy проблемы

**Проблема:**
```
ProxyError: Cannot connect to proxy
ConnectionError: Failed to establish connection
```

**Workaround:**
```bash
export http_proxy="http://proxy.company.com:8080"
export https_proxy="http://proxy.company.com:8080"
export no_proxy="localhost,127.0.0.1"

# Для Git:
git config --global http.proxy http://proxy.company.com:8080
git config --global https.proxy http://proxy.company.com:8080
```

### 4. NTLM аутентификация

**Проблема:**
```
NTLMError: Cannot determine NTLM username
UnauthorizedError: 401 Unauthorized
```

**Решение:**
```bash
export EWS_USER_UPN="user@company.com"
export EWS_USER_LOGIN="user"
export EWS_USER_DOMAIN="COMPANY"
```

### 5. Timeouts с большими объемами

**Проблема:**
```
ConnectionTimeout: Request timeout after 300s
ReadTimeout: Read timed out
```

**Workaround:**
```yaml
# В config.yaml:
llm:
  timeout: 600  # Увеличить до 10 минут
  
# Или обрабатывать меньше писем:
time:
  lookback_hours: 24  # Вместо 48
```

---

## Пример вывода doctor.sh с ошибками

```
======================================
  ActionPulse Environment Doctor
======================================

Проверка Python...
✓ Python 3.11.4 найден

Проверка Git...
✓ Git 2.39.2 найден

Проверка виртуального окружения...
✓ Виртуальное окружение найдено в digest-core/.venv
✗ Виртуальное окружение не активировано
  ℹ Активируйте: source digest-core/.venv/bin/activate

Проверка переменных окружения...
✓ EWS_ENDPOINT = https://owa.company.com/EWS/Exchange.asmx
✓ EWS_USER_UPN = user@company.com
✓ EWS_PASSWORD установлена (***)
✗ LLM_ENDPOINT не установлена (обязательная)
✗ LLM_TOKEN не установлена (обязательная)

Проверка конфигурационного файла...
✓ config.yaml найден
⚠ config.yaml имеет ошибки синтаксиса

Проверка рабочих директорий...
✓ OUT_DIR существует и доступна для записи
✗ STATE_DIR не существует
  ℹ Создайте: mkdir -p $HOME/.digest-state
⚠ TMPDIR существует, но недоступна для записи
  ℹ Исправьте: chmod 755 /tmp/

Проверка сетевого подключения...
✓ Доступ к EWS (https://owa.company.com/EWS/Exchange.asmx)
⚠ Нет доступа к LLM Gateway (https://llm-gw.company.com/api/v1/chat)

Проверка SSL сертификатов...
⚠ CA сертификат не указан в config.yaml

Проверка дискового пространства...
⚠ Свободное место: 250 MB (рекомендуется >500 MB)

======================================
  Итоги диагностики
======================================
✓ Успешно: 8
⚠ Предупреждений: 5
✗ Ошибок: 4

✗ Обнаружены критические ошибки!

Исправьте ошибки, затем запустите снова: ./digest-core/scripts/doctor.sh
```

---

## Когда использовать этот шаблон

✅ **Используйте этот шаблон, если:**
- Были критические ошибки, препятствующие работе
- Тесты не завершились успешно
- `doctor.sh` показал ошибки ✗
- Требуются изменения в коде для исправления

⚠️ **Важно:**
- Включайте максимум деталей для воспроизведения
- Предлагайте конкретные решения
- Не скрывайте проблемы - они важны для улучшения

---

## См. также

- [Пример успешного отчета](./successful_test_report.md)
- [Специфика корпоративных ноутбуков](./corporate_laptop_setup.md)
- [Troubleshooting Guide](../../troubleshooting/TROUBLESHOOTING.md)
- [E2E Testing Guide (архив)](../../legacy/E2E_TESTING_GUIDE.md)


