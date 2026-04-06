# End-to-End Testing Guide для ActionPulse

> **🗄️ ARCHIVED 2026-04-06.** Этот документ ссылается на shell-скрипты
> (`install_interactive.sh`, `doctor.sh`, `test_run.sh`), которые никогда
> не существовали в репозитории. Сохранён для исторической справки.
>
> **Текущий путь тестирования:** `cd digest-core && make test` (mocked tests),
> `make smoke` (dry-run), `python -m digest_core.cli diagnose` (диагностика),
> `digest-core/scripts/collect_diagnostics.sh` (сбор архива).
> Полная инструкция по setup — [`README.md`](../../README.md) и
> [`digest-core/CLAUDE.md`](../../digest-core/CLAUDE.md).

## Введение

Этот гайд предназначен для **тестировщиков**, которые устанавливают и тестируют ActionPulse на отдельном компьютере (в том числе корпоративном ноутбуке) для проверки работоспособности и возврата результатов разработчику.

**Целевая аудитория:**
- QA-инженеры
- Тестировщики на корпоративных ноутбуках
- Пользователи, выполняющие первичную установку

**Что вы получите в результате:**
- Полностью настроенную систему ActionPulse
- Результаты тестирования (логи, метрики, дайджесты)
- Архив диагностики для отправки разработчику

**Время выполнения:** ~30 минут

---

## Требования

### Минимальные системные требования

- **ОС:** macOS, Linux (Ubuntu/Debian/CentOS), или Windows с WSL
- **RAM:** 2 GB (рекомендуется 4 GB)
- **Диск:** 500 MB свободного места
- **Сеть:** Доступ к интернету для установки зависимостей

### Необходимые права доступа

- Чтение/запись в домашнюю директорию (`$HOME`)
- Возможность создания директорий в `$HOME`
- Права на выполнение скриптов

### Что должно быть доступно

- **Учетные данные Exchange:**
  - Email адрес (UPN): `user@company.com`
  - Пароль от почты
  - URL сервера EWS: `https://owa.company.com/EWS/Exchange.asmx`
  
- **Токен LLM Gateway:**
  - URL endpoint: `https://llm-gw.company.com/api/v1/chat`
  - Bearer токен для авторизации

> **Примечание:** Если у вас нет учетных данных, можете протестировать установку в dry-run режиме (без реального подключения к EWS и LLM).

### Специфика корпоративных ноутбуков

Если вы работаете на корпоративном ноутбуке, возможны следующие ограничения:

- ❌ **Нет доступа к `/tmp/`** → Используем `$HOME/.digest-temp`
- ❌ **Нет доступа к `/etc/ssl/`** → Размещаем сертификаты в `$HOME/.ssl`
- ❌ **Нет доступа к `/opt/`** → Устанавливаем в `$HOME/ActionPulse`
- ⚠️ **Корпоративный прокси** → Может потребоваться настройка
- ⚠️ **Самоподписанные сертификаты** → Настраиваем trust chain

Все эти случаи покрыты в разделе [Troubleshooting](#troubleshooting).

---

## Шаг 1: Подготовка окружения

### 1.1. Проверка установленных инструментов

Откройте терминал и выполните:

```bash
# Проверка Git
git --version
# Ожидается: git version 2.x.x

# Проверка Python (нужна версия 3.11 или выше)
python3 --version
# Ожидается: Python 3.11.x или выше
```

**Если Git отсутствует:**
```bash
# macOS
brew install git

# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y git

# CentOS/RHEL
sudo yum install -y git
```

**Если Python 3.11+ отсутствует:**
```bash
# macOS
brew install python@3.11

# Ubuntu/Debian (может потребоваться добавление PPA)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv

# После установки проверьте:
python3.11 --version
```

### 1.2. Настройка путей для корпоративного ноутбука

Создайте директории в домашней папке (это обойдет ограничения прав):

```bash
# Создаем рабочие директории
mkdir -p "$HOME/.digest-out"      # Для результатов дайджестов
mkdir -p "$HOME/.digest-state"    # Для состояния синхронизации
mkdir -p "$HOME/.digest-temp"     # Для временных файлов
mkdir -p "$HOME/.digest-logs"     # Для логов

# Экспортируем переменные окружения
export OUT_DIR="$HOME/.digest-out"
export STATE_DIR="$HOME/.digest-state"
export TMPDIR="$HOME/.digest-temp"

# Проверяем права
ls -la "$HOME" | grep digest
```

**Ожидаемый результат:** Вы должны увидеть созданные директории с правами `drwxr-xr-x`.

### 1.3. Настройка прокси (если необходимо)

Если ваша корпоративная сеть требует прокси:

```bash
# HTTP/HTTPS прокси
export http_proxy="http://proxy.company.com:8080"
export https_proxy="http://proxy.company.com:8080"
export no_proxy="localhost,127.0.0.1"

# Для Git
git config --global http.proxy http://proxy.company.com:8080
git config --global https.proxy http://proxy.company.com:8080

# Проверка
curl -I https://github.com
```

---

## Шаг 2: Клонирование и установка

### 2.1. Автоматическая установка (рекомендуется)

```bash
# Полная установка с интерактивной настройкой
curl -fsSL https://raw.githubusercontent.com/ruspg/ActionPulse/main/digest-core/scripts/install_interactive.sh | bash

# Или если репозиторий приватный/локальный, склонируйте вручную:
git clone https://github.com/ruspg/ActionPulse.git
cd ActionPulse
./digest-core/scripts/install_interactive.sh
```

**Что делает скрипт:**
- ✅ Проверяет зависимости (Python, Git)
- ✅ Создает виртуальное окружение в `digest-core/.venv`
- ✅ Устанавливает Python пакеты
- ✅ Запускает интерактивный мастер настройки

**Если скрипт не работает**, переходите к ручной установке ниже.

### 2.2. Ручная установка

```bash
# 1. Клонирование репозитория
git clone https://github.com/ruspg/ActionPulse.git
cd ActionPulse

# 2. Переход в директорию digest-core
cd digest-core

# 3. Создание виртуального окружения
python3.11 -m venv .venv

# 4. Активация виртуального окружения
source .venv/bin/activate

# 5. Обновление pip
pip install --upgrade pip setuptools wheel

# 6. Установка зависимостей
pip install -e .

# Если есть проблемы с SSL сертификатами:
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .
```

### 2.3. Проверка установки

```bash
# Проверка CLI
python3.11 -m digest_core.cli --help

# Ожидаемый результат: вывод справки по командам
```

Если вы видите справку, установка прошла успешно! ✅

---

## Шаг 3: Настройка конфигурации

### 3.1. Создание конфигурационного файла

```bash
# Убедитесь, что вы в директории digest-core
cd ~/ActionPulse/digest-core

# Скопируйте пример конфигурации
cp configs/config.example.yaml configs/config.yaml
```

### 3.2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```bash
cd ~/ActionPulse

cat > .env << 'EOF'
# EWS Configuration
export EWS_ENDPOINT="https://owa.company.com/EWS/Exchange.asmx"
export EWS_USER_UPN="your.email@company.com"
export EWS_USER_LOGIN="your_username"
export EWS_USER_DOMAIN="company.com"
export EWS_PASSWORD="your_password_here"

# LLM Configuration
export LLM_ENDPOINT="https://llm-gw.company.com/api/v1/chat"
export LLM_TOKEN="your_llm_token_here"

# Output directories
export OUT_DIR="$HOME/.digest-out"
export STATE_DIR="$HOME/.digest-state"
EOF

# Сделайте файл приватным
chmod 600 .env

# Загрузите переменные
source .env
```

**⚠️ ВАЖНО:** Замените значения на ваши реальные учетные данные!

### 3.3. Проверка конфигурации

Запустите скрипт диагностики:

```bash
cd ~/ActionPulse
./digest-core/scripts/doctor.sh
```

**Ожидаемый вывод:**
```
✓ Python 3.11+ найден
✓ Виртуальное окружение активно
✓ Переменные окружения установлены
✓ Конфигурационный файл найден
✓ Директории созданы
```

Если все пункты отмечены ✓, переходите к следующему шагу.

---

## Шаг 4: Smoke-тестирование

### 4.1. Запуск dry-run режима

Dry-run режим проверяет подключение к EWS и нормализацию данных **без вызовов LLM**:

```bash
cd ~/ActionPulse/digest-core
source ../.env
source .venv/bin/activate

# Запуск в dry-run режиме
python3.11 -m digest_core.cli run --dry-run
```

**Ожидаемые результаты:**

✅ **Успешный запуск:**
```
INFO: Dry-run mode: ingest+normalize only
INFO: Connecting to EWS endpoint: https://owa.company.com/EWS/Exchange.asmx
INFO: Successfully authenticated
INFO: Fetching emails from Inbox
INFO: Found 15 emails
INFO: Normalizing emails...
INFO: Dry-run completed (exit code 2 is expected)
```

❌ **Ошибки подключения:**
- Если видите `SSL certificate verification failed` → см. [Troubleshooting: SSL проблемы](#ssl-сертификаты)
- Если видите `NTLM authentication failed` → проверьте учетные данные
- Если видите `Cannot determine NTLM username` → проверьте `EWS_USER_UPN`

### 4.2. Проверка нормализации данных

После успешного dry-run проверьте логи:

```bash
# Найти последний лог
ls -lt "$HOME/.digest-logs/" | head -5

# Посмотреть содержимое
tail -50 "$HOME/.digest-logs/run-*.log"
```

Вы должны увидеть:
- ✅ Подключение к EWS
- ✅ Получение писем
- ✅ Нормализация HTML → текст
- ✅ Удаление цитат

---

## Шаг 5: Полное тестирование

### 5.1. Запуск полного цикла

Теперь запустим полный цикл с LLM для генерации дайджеста:

```bash
cd ~/ActionPulse/digest-core

# Автоматический тестовый запуск с диагностикой
./digest-core/scripts/test_run.sh
```

**Что происходит:**
1. ✅ Проверка переменных окружения
2. ✅ Запуск диагностики окружения
3. ✅ Подключение к EWS и получение писем
4. ✅ Нормализация и обработка
5. ✅ Вызов LLM для извлечения действий
6. ✅ Генерация JSON и Markdown дайджестов
7. ✅ Автоматический сбор диагностики

**Время выполнения:** 3-10 минут (зависит от количества писем)

### 5.2. Проверка результатов

После завершения проверьте созданные файлы:

```bash
# Список результатов
ls -lh "$HOME/.digest-out/"

# Ожидается:
# digest-2024-10-13.json  # Структурированные данные
# digest-2024-10-13.md    # Человеко-читаемый дайджест
```

**Просмотр дайджеста:**
```bash
# Markdown версия
cat "$HOME/.digest-out/digest-$(date +%Y-%m-%d).md"

# JSON версия (с форматированием)
cat "$HOME/.digest-out/digest-$(date +%Y-%m-%d).json" | jq '.'
```

### 5.3. Проверка метрик

```bash
# Метрики Prometheus (если запущены)
curl http://localhost:9108/metrics 2>/dev/null | grep digest_

# Health check
curl http://localhost:9109/healthz 2>/dev/null
```

---

## Шаг 6: Сбор диагностики

### 6.1. Автоматический сбор

Скрипт `test_run.sh` автоматически собирает диагностику. Но вы можете запустить сбор вручную:

```bash
cd ~/ActionPulse/digest-core
./digest-core/scripts/collect_diagnostics.sh
```

**Что собирается:**
- 📋 Системная информация (ОС, Python версия)
- 📊 Метрики Prometheus
- 📝 Логи приложения
- ⚙️ Конфигурация (без секретов!)
- 📄 Выходные файлы (digest JSON/MD)
- 🔍 Переменные окружения (санитизированные)

### 6.2. Поиск архива диагностики

```bash
# Архив создается в:
ls -lh "$HOME/.digest-temp/diagnostics-*.tar.gz"

# Показать последний созданный
ls -t "$HOME/.digest-temp/diagnostics-*.tar.gz" | head -1
```

**Формат имени:** `diagnostics-YYYY-MM-DD-HH-MM-SS.tar.gz`

### 6.3. Проверка содержимого архива

```bash
# Посмотреть содержимое без распаковки
tar -tzf "$HOME/.digest-temp/diagnostics-2024-10-13-10-30-00.tar.gz"

# Проверить размер (должен быть < 25MB для email)
du -h "$HOME/.digest-temp/diagnostics-2024-10-13-10-30-00.tar.gz"
```

### 6.4. Безопасность

**Что автоматически удаляется из архива:**
- ❌ Пароли (`EWS_PASSWORD`)
- ❌ Токены (`LLM_TOKEN`)
- ❌ Email адреса (маскируются как `***@***.***`)
- ❌ Содержимое писем (только метаданные)

**Что включается:**
- ✅ Версии ПО
- ✅ Параметры конфигурации (без секретов)
- ✅ Метрики производительности
- ✅ Структура выходных файлов
- ✅ Коды ошибок и stack traces

---

## Шаг 7: Возврат результатов

### 7.1. Подготовка к отправке

Найдите созданный архив:
```bash
DIAG_FILE=$(ls -t "$HOME/.digest-temp/diagnostics-*.tar.gz" | head -1)
echo "Архив для отправки: $DIAG_FILE"
```

### 7.2. Способы передачи результатов

#### Способ 1: Email (рекомендуется)

**Тема письма:**
```
ActionPulse Test Results - 2024-10-13
```

**Шаблон письма:**
```
Здравствуйте!

Провел end-to-end тестирование ActionPulse на [название системы, например: корпоративный ноутбук macOS].

=== РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ===

✓ Установка: Успешно
✓ Конфигурация: Успешно
✓ Smoke-тесты (dry-run): Успешно
✓ Полный цикл: Успешно
✓ Сбор диагностики: Успешно

=== МЕТРИКИ ===

- Время выполнения полного цикла: [укажите, например: 5 минут]
- Обработано писем: [количество, например: 23]
- Создано секций в дайджесте: [например: 3]
- Размер дайджеста: [например: 2.5 KB]

=== НАЙДЕННЫЕ ПРОБЛЕМЫ ===

[Опишите проблемы, если были, или напишите "Проблем не обнаружено"]

=== СИСТЕМНАЯ ИНФОРМАЦИЯ ===

- ОС: [например: macOS 14.6.0]
- Python: [например: 3.11.5]
- Доступ к Exchange: OK
- Доступ к LLM Gateway: OK

Прикреплен архив диагностики: diagnostics-2024-10-13-10-30-00.tar.gz

С уважением,
[Ваше имя]
```

**Отправка:**
1. Откройте корпоративную почту (Outlook/Gmail/другую)
2. Создайте новое письмо
3. Скопируйте шаблон выше
4. Прикрепите архив диагностики
5. Отправьте на адрес разработчика

#### Способ 2: Файловая система

```bash
# Скопировать в общую папку
cp "$DIAG_FILE" /path/to/shared/folder/

# Или на сетевой диск
cp "$DIAG_FILE" /Volumes/SharedDrive/ActionPulse-Testing/
```

#### Способ 3: USB-носитель

```bash
# Подключите USB
# Найдите точку монтирования (например, /Volumes/USB)

cp "$DIAG_FILE" /Volumes/USB/
```

### 7.3. Чек-лист перед отправкой

- [ ] Архив собран успешно
- [ ] Размер архива проверен (< 25 MB для email)
- [ ] Секретные данные не включены (проверено автоматически)
- [ ] Заполнен шаблон отчета
- [ ] Описаны все найденные проблемы
- [ ] Указаны версии ПО и ОС
- [ ] Прикреплен архив к письму

---

## Troubleshooting

### SSL сертификаты

**Проблема:** `SSL certificate verification failed`

**Решение для корпоративных сертификатов:**

```bash
# 1. Получите корпоративный CA сертификат
# Обычно это файл вида corp-ca.crt или corp-root-ca.pem

# 2. Скопируйте его в домашнюю директорию
mkdir -p "$HOME/.ssl"
cp /path/to/corp-ca.crt "$HOME/.ssl/corp-ca.pem"

# 3. Обновите config.yaml
nano ~/ActionPulse/digest-core/configs/config.yaml

# Добавьте/измените:
ews:
  verify_ca: "$HOME/.ssl/corp-ca.pem"
  verify_ssl: true
```

**Временный обход (только для тестирования!):**
```yaml
ews:
  verify_ssl: false  # ТОЛЬКО ДЛЯ ТЕСТИРОВАНИЯ
```

### Проблемы с правами доступа

**Проблема:** `Permission denied` при создании файлов

**Решение:**
```bash
# Все пути в домашнюю директорию
export OUT_DIR="$HOME/.digest-out"
export STATE_DIR="$HOME/.digest-state"
export TMPDIR="$HOME/.digest-temp"

# Создайте директории
mkdir -p "$OUT_DIR" "$STATE_DIR" "$TMPDIR"

# Установите правильные права
chmod 755 "$OUT_DIR" "$STATE_DIR" "$TMPDIR"

# Запустите снова
cd ~/ActionPulse/digest-core
./digest-core/scripts/test_run.sh
```

### Проблемы с Python версией

**Проблема:** `Python 3.11+ required`

**Решение для macOS:**
```bash
# Установка через Homebrew
brew install python@3.11

# Добавление в PATH (временно)
export PATH="$(brew --prefix)/opt/python@3.11/bin:$PATH"

# Проверка
python3.11 --version

# Запуск с явным указанием python3.11
python3.11 -m digest_core.cli run --dry-run
```

**Решение для Ubuntu:**
```bash
# Добавление PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev

# Проверка
python3.11 --version
```

### NTLM аутентификация

**Проблема:** `Cannot determine NTLM username`

**Решение:**
```bash
# Убедитесь, что установлены ВСЕ переменные:
export EWS_USER_UPN="user@company.com"       # Email адрес
export EWS_USER_LOGIN="user"                 # Логин (без домена)
export EWS_USER_DOMAIN="company.com"         # Домен

# Или укажите в config.yaml:
ews:
  user_upn: "user@company.com"
  ntlm_username: "DOMAIN\\user"  # Windows стиль
```

### Пустой дайджест

**Проблема:** Дайджест создается, но пустой (нет писем)

**Возможные причины:**
1. Временное окно не покрывает письма
2. Папка Inbox пустая или неправильное имя

**Решение:**
```bash
# 1. Проверьте временное окно в config.yaml
cat ~/ActionPulse/digest-core/configs/config.yaml | grep -A 5 "time:"

# 2. Попробуйте увеличить lookback_hours:
# В config.yaml:
time:
  lookback_hours: 48  # Вместо 24

# 3. Проверьте папки EWS
# В config.yaml:
ews:
  folders:
    - "Inbox"
    - "Sent Items"  # Добавьте другие папки
```

### Архив диагностики слишком большой

**Проблема:** Размер архива > 25 MB

**Решение:**
```bash
# Исключите большие файлы при сборе
cd ~/ActionPulse/digest-core
./digest-core/scripts/collect_diagnostics.sh --exclude-large

# Или сожмите сильнее
gzip -9 diagnostics-folder.tar
```

---

## FAQ

**Q: Могу ли я запустить тестирование без реальных учетных данных?**
A: Да, используйте `--dry-run` режим. Он не требует LLM токена.

**Q: Сколько времени занимает полный цикл?**
A: От 3 до 10 минут в зависимости от количества писем (обычно 5-7 минут).

**Q: Безопасно ли отправлять архив диагностики?**
A: Да, все секретные данные автоматически удаляются из архива.

**Q: Что делать, если test_run.sh падает с ошибкой?**
A: Запустите `./digest-core/scripts/doctor.sh` для диагностики, затем см. раздел Troubleshooting.

**Q: Нужны ли права sudo?**
A: Нет, вся установка происходит в домашней директории.

**Q: Можно ли запускать на Windows?**
A: Да, через WSL (Windows Subsystem for Linux). Установите WSL, затем следуйте инструкциям как для Linux.

---

## Следующие шаги

После успешного тестирования:

1. **Отправьте результаты** согласно [Шагу 7](#шаг-7-возврат-результатов)
2. **Сохраните архив диагностики** локально на случай дополнительных вопросов
3. **Оставьте установленную систему** для повторного тестирования (если потребуется)

## Дополнительные ресурсы

- 📋 [Детальный чек-лист тестирования](../../docs/testing/MANUAL_TESTING_CHECKLIST.md)
- 📧 [Руководство по отправке результатов](../../docs/testing/SEND_RESULTS.md)
- 🔧 [Подробное руководство по установке](../installation/INSTALL.md)
- 🚨 [Полное руководство по troubleshooting](../troubleshooting/TROUBLESHOOTING.md)
- 📚 [Полная документация проекта](../README.md)

---

**Спасибо за тестирование ActionPulse!** 🎉

Если возникли вопросы или проблемы, не описанные в этом гайде, пожалуйста, включите их в отчет о тестировании.


