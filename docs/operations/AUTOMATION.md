# ActionPulse Automation Guide

Руководство по автоматизации запуска ActionPulse. **Эталонные юниты и пример cron** лежат в репозитории: `digest-core/deploy/` (`actionpulse-digest@.service`, `actionpulse-digest.timer`, `crontab.example`, `install-systemd.sh`, `env.example`).

## systemd (рекомендуется: user units)

Штатный сценарий — **user timer** (без root), как в `install-systemd.sh`:

1. Подготовить `~/.config/actionpulse/env` (секреты). Шаблон: `digest-core/deploy/env.example`.
2. Из каталога `digest-core/deploy/` выполнить **`./install-systemd.sh`** под целевым пользователем.
3. Юниты копируются в `~/.config/systemd/user/` как **`actionpulse-digest@.service`** и **`actionpulse-digest.timer`**.

### Содержимое сервиса (сводка)

Файл `actionpulse-digest.service` в репозитории задаёт:

- `Type=oneshot`, `User=%i` (instance — имя пользователя)
- `WorkingDirectory=%h/ActionPulse/digest-core`
- `ExecStart=.../.venv/bin/python -m digest_core.cli run --from-date today --sources ews`
- `EnvironmentFile=-%h/.config/actionpulse/env`

Запуск вручную для пользователя `alice`:

```bash
systemctl --user start actionpulse-digest@alice.service
```

Таймер `actionpulse-digest.timer`: по умолчанию **`OnCalendar=*-*-* 08:00:00`**, `RandomizedDelaySec=120`.

```bash
systemctl --user enable --now actionpulse-digest.timer
systemctl --user list-timers
journalctl --user -u 'actionpulse-digest@*' -f
```

### Чего не делать

- **Не** подставляйте секреты через `%i` в `Environment=` — в systemd **`%i` — это имя инстанса** шаблонного юнита, не пароль и не токен.
- Старые примеры с `digest-core.service` в `/etc`, Docker-only `ExecStart` и `EnvironmentFile=/etc/digest-core.env` **не совпадают** с текущими файлами в `digest-core/deploy/`; используйте репозиторий как SoT.

## Cron

Пример из `digest-core/deploy/crontab.example`:

```cron
0 8 * * 1-5  . ~/.config/actionpulse/env && cd ~/ActionPulse/digest-core && .venv/bin/python -m digest_core.cli run --from-date today --sources ews >> ~/actionpulse-cron.log 2>&1
```

Секреты загружаются из **`~/.config/actionpulse/env`**, не из `source ../.env` в корне монорепо (если только вы сами так не настроили).

## Docker / opt paths

Запуск через Docker по-прежнему возможен (см. `docs/operations/DEPLOYMENT.md`), но **это отдельный** сценарий от user-systemd файлов выше.

## State management

```bash
cd digest-core
./scripts/rotate_state.sh
# или
make rotate
```

## Мониторинг timer

Имя таймера в штатной установке — **`actionpulse-digest.timer`**, не `digest-core.timer`:

```bash
systemctl --user is-active actionpulse-digest.timer
```

## See Also

- [DEPLOYMENT.md](DEPLOYMENT.md)
- [MONITORING.md](MONITORING.md)
- [Troubleshooting](../troubleshooting/TROUBLESHOOTING.md)
