# ActionPulse Deployment Guide

Руководство по развертыванию ActionPulse в различных средах.

## Dedicated Machine Setup

Для развертывания на выделенной машине с доступом к EWS:

### Prerequisites

- Docker/Podman установлен
- Доступ к EWS endpoint
- Корпоративный CA сертификат в `/etc/ssl/corp-ca.pem`
- Директории `/opt/digest/out` и `/opt/digest/.state` (UID 1001)

### Build and Run

```bash
# Build Docker image
make docker

# Run container with proper mounts
docker run -d \
  --name digest-core \
  -e EWS_PASSWORD='your_password' \
  -e LLM_TOKEN='your_token' \
  -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro \
  -v /opt/digest/out:/data/out \
  -v /opt/digest/.state:/data/.state \
  -p 9108:9108 \
  -p 9109:9109 \
  digest-core:latest
```

### Manual Run

```bash
docker run -it \
  -e EWS_PASSWORD='your_password' \
  -e LLM_TOKEN='your_token' \
  -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro \
  -v /opt/digest/out:/data/out \
  -v /opt/digest/.state:/data/.state \
  -p 9108:9108 \
  -p 9109:9109 \
  digest-core:latest python -m digest_core.cli run
```

## Docker Setup

### Build Image

```bash
# Build image
make docker

# Run container
docker run --rm \
  -e EWS_PASSWORD=$EWS_PASSWORD \
  -e LLM_TOKEN=$LLM_TOKEN \
  -v $(pwd)/out:/data/out \
  -p 9108:9108 \
  -p 9109:9109 \
  digest-core:latest
```

### Docker Automation

```bash
# Ежедневный запуск через Docker
0 8 * * * docker run --rm \
  -e EWS_PASSWORD='password' \
  -e LLM_TOKEN='token' \
  -v /path/to/out:/data/out \
  -v /path/to/.state:/data/.state \
  digest-core:latest
```

## Infrastructure Requirements

### Network Access

- **EWS Endpoint**: HTTPS доступ к Exchange Web Services
- **LLM Gateway**: HTTPS доступ к LLM API
- **Corporate CA**: Корпоративный сертификат для TLS

### Storage

- **Output Directory**: `/opt/digest/out` для результатов
- **State Directory**: `/opt/digest/.state` для синхронизации
- **Permissions**: UID 1001 (non-root)

### Security

- **Non-root Container**: Docker запускается от UID 1001
- **Secret Management**: Credentials только через ENV
- **TLS Verification**: Проверка с корпоративным CA
- **Volume Mounts**: Read-only для сертификатов

## Environment Variables

### Required

```bash
EWS_PASSWORD="your_ews_password"
EWS_USER_UPN="user@corp.com"
EWS_ENDPOINT="https://ews.corp.com/EWS/Exchange.asmx"
LLM_TOKEN="your_llm_token"
LLM_ENDPOINT="https://llm-gw.corp.com/api/v1/chat"
```

### Optional

- **`DIGEST_CONFIG_PATH`** — переопределить путь к YAML-конфигу (см. `config.py`).
- Порт **Prometheus** задаётся в конфиге **`observability.prometheus_port`** (по умолчанию 9108), не отдельной переменной окружения в стиле `PROMETHEUS_PORT`.
- Порт **health HTTP** сейчас **9109** и задан в коде (`run.py` + `healthz.py`), отдельного `HEALTH_PORT` в конфиге нет.
- Уровень логов — флаг CLI **`--log-level`**, не `DIGEST_LOG_LEVEL`.

## Port Configuration

- **9108**: Prometheus metrics
- **9109**: Health checks

## Troubleshooting

### Permission Issues

```bash
# Fix directory permissions
sudo mkdir -p /opt/digest/out /opt/digest/.state
sudo chown -R 1001:1001 /opt/digest/
sudo chmod -R 755 /opt/digest/
```

### Port Conflicts

```bash
# Check what's using the ports
lsof -i :9108
lsof -i :9109

# Use different ports
docker run -p 9109:9109 -p 9108:9108 ...
```

### Certificate Issues

```bash
# Check if CA certificate exists
ls -la /etc/ssl/corp-ca.pem

# Verify certificate
openssl x509 -in /etc/ssl/corp-ca.pem -text -noout
```

## See Also

- [AUTOMATION.md](AUTOMATION.md) - Настройка автоматизации
- [MONITORING.md](MONITORING.md) - Мониторинг и observability
- [Troubleshooting](../troubleshooting/TROUBLESHOOTING.md) — общее руководство
