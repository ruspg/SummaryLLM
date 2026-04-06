## 📡 Подключение к почте (Exchange on-prem, EWS/NTLM)

### 1. Архитектура доступа

- Источник: **Microsoft Exchange Server on-premises**, версия 2013+ (EWS API).
    
- Endpoint: `https://owa.<corp-domain>.ru/EWS/Exchange.asmx` (порт 443).
    
- Аутентификация: **NTLM (Integrated Windows Authentication)** или Basic (логин/пароль).
    
    - Заголовки при `curl -I` показывают: `WWW-Authenticate: Negotiate, NTLM`.
        
    - OAuth недоступен, `X-OAuth-Enabled: True`, но фактически сервер требует NTLM.
        
- Доступ тестировался через `curl` и библиотеку `exchangelib` — ответ 200 при NTLM-авторизации.
    
- Службы каталога доступны по `ldap://directoryservice:<3268>` — но пока не используются.
    

### 2. Форматы учётных данных

- Работают два формата:
    
    1. **UPN (рекомендуемый)** — `login@corp-domain.ru`
        
    2. **Domain\Username** — `MSK\login`
        
- `.local` в домене **не требуется**.
    
- Для NTLM-авторизации пароль передаётся в открытом NTLM-хендшейке (внутри сети, TLS).
    
- Тестовые логины проверены: HTTP 200 на `login@xxx.ru` и `login`.
    

### 3. Проверка соединения

```bash
curl --ntlm -u 'login@xxx.ru:password' \
     https://owa.xxx.ru/EWS/Exchange.asmx -v
```

Ответ HTTP 200 подтверждает успешный NTLM-handshake.

Для диагностики статуса NTLM:

```bash
curl -I https://owa.xxx.ru/EWS/Exchange.asmx
# должен вернуть WWW-Authenticate: NTLM
```

### 4. Используемая библиотека

- **Python:** [`exchangelib`](https://ecederstrand.github.io/exchangelib/), поддерживает NTLM.
    
    ```python
    from exchangelib import Credentials, Account, Configuration, DELEGATE, NTLM
    creds = Credentials(username="login@xxx.ru", password="****")
    config = Configuration(server="owa.xxx.ru", credentials=creds, auth_type=NTLM)
    account = Account(primary_smtp_address="login@xxx.ru",
                      credentials=creds, config=config,
                      autodiscover=False, access_type=DELEGATE)
    ```
    
- Проверено, что соединение не требует `autodiscover=True` — прямое указание сервера достаточно.
    
- Для Docker-среды добавлены сертификаты корпоративного CA (`ca-certificates` пакет в образе).
    
- Требуется TLS-доверие к корпоративному CA, **без `--insecure`**.
    

### 5. Выборка данных

- Базовая выборка: `account.inbox.filter(datetime_received__gte=start_date)`
    
- Сортировка: `order_by('-datetime_received')`
    
- Ограничение количества: `[:MAX_ITEMS]`.
    
- Схема извлекаемых полей:
    
    - `datetime_received`, `sender.email_address`, `subject`, `text_body`, `conversation_id`.
        
    - Для трассировки: `id`, `changekey`, `folder`, `is_read`.
        
- Поддержка часового пояса ящика через `account.default_timezone`.
    

### 6. Контроль состояния и инкрементальность

- Используется EWS `SyncState` или `(itemId, changeKey)` для high-water mark.
    
- Повторная выборка за последние 48 ч для дедупликации.
    
- Дедуп по `hash_sha1` от `(conversation_id + subject + datetime_received)`.
    

### 7. Безопасность и политика

- Доступ осуществляется из внутренней сети, без проброса наружу.
    
- Секреты (логин/пароль) для ActionPulse задаются через ENV: по умолчанию пароль читается из **`EWS_PASSWORD`** (или имя из `ews.password_env` в YAML), см. `digest_core/config.py` и `deploy/env.example`.
    
- Логи не содержат значений полей `EXCH_PASS`.
    
- Проверено доверие к сертификатам (установлен `ca-certificates` в контейнере).
    
- Поддерживается аудит подключений на сервере Exchange.
    

### 8. Диагностика и fallback

|Сценарий|Поведение|
|---|---|
|Неверный пароль / 401|возвращается понятная ошибка «Auth failed», воркфлоу завершается.|
|Нет соединения / timeout|повтор через backoff (до 1 раза), маркировка «частичный отчёт».|
|Ошибка SSL|проверка цепочки CA, оповещение, не игнорируется `--insecure`.|

---

**Резюме:**  
Доступ к почте построен на NTLM-аутентификации к `EWS/Exchange.asmx` через библиотеку `exchangelib`.  
Формат логина — `login@domain.ru` или `DOMAIN\login`.  
TLS-доверие к корпоративному CA обеспечено.  
Для инкрементального сбора используется `SyncState`/`itemId`.  
Все параметры подключений хранятся в переменных окружения и не пишутся в логи.