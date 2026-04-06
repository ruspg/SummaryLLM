# Troubleshooting Guide

## Common Issues and Solutions

### 1. Configuration Errors

#### Error: "Field required [type=missing, input_value={}, input_type=dict]"

**Cause**: Missing required configuration values for EWS or LLM.

**Solution**:
```bash
# Verify the wizard env file exists and contains the required keys.
# (The interactive setup wizard writes secrets to ~/.config/actionpulse/env
# with chmod 600. See README.md / `make setup`.)
ls -l ~/.config/actionpulse/env
grep -E '^(EWS_|LLM_|MM_)' ~/.config/actionpulse/env | sed 's/=.*/=<set>/'

# Ensure all required variables are present:
# EWS_PASSWORD=your_password
# EWS_USER_UPN=user@corp.com
# EWS_ENDPOINT=https://ews.corp.com/EWS/Exchange.asmx
# LLM_TOKEN=your_token
# LLM_ENDPOINT=https://llm-gw.corp.com/api/v1/chat
# MM_WEBHOOK_URL=https://mattermost.corp.com/hooks/...

# Re-run the wizard if any are missing:
cd digest-core && python -m digest_core.cli setup

# Then load the env into the current shell session:
set -a && source ~/.config/actionpulse/env && set +a
```

#### Error: "python-dotenv could not parse statement"

**Cause**: Invalid syntax in `~/.config/actionpulse/env` (or another env file
loaded by your shell). Note: ActionPulse itself does not parse a project-root
`.env` file at runtime — secrets come from the environment, populated by the
wizard-managed file above.

**Solution**:
- Re-run the wizard so the file is regenerated correctly: `python -m digest_core.cli setup`
- Or fix manually: remove quotes around values (`PASSWORD=value` not `PASSWORD="value"`),
  no spaces around `=`, and use `#` for comments (not `//`)

### 2. EWS Connection Issues

#### Error: "SSL certificate verification failed"

**Cause**: Corporate CA certificate not found or invalid.

**Solution**:
```bash
# Check if CA certificate exists
ls -la /etc/ssl/corp-ca.pem

# Verify certificate
openssl x509 -in /etc/ssl/corp-ca.pem -text -noout

# Update config to point to correct path
# In config.yaml: verify_ca: "/path/to/your/corp-ca.pem"
```

#### Error: "NTLM authentication failed"

**Cause**: Invalid credentials or UPN format.

**Solution**:
```bash
# Verify UPN format (should include domain)
echo $EWS_USER_UPN  # Should be: user@corp.com

# Test credentials manually
python3 -c "
from exchangelib import Credentials, Account
creds = Credentials('$EWS_USER_UPN', '$EWS_PASSWORD')
print('Credentials created successfully')
"
```

### 3. LLM Gateway Issues

#### Error: "HTTP 401 Unauthorized"

**Cause**: Invalid or expired LLM token.

**Solution**:
```bash
# Check token format
echo $LLM_TOKEN | wc -c  # Should be reasonable length

# Test token manually
curl -H "Authorization: Bearer $LLM_TOKEN" "$LLM_ENDPOINT/health"
```

#### Error: "HTTP 429 Too Many Requests"

**Cause**: Rate limiting from LLM Gateway.

**Solution**:
- Wait before retrying
- Check if you have multiple instances running
- Verify rate limits in LLM Gateway configuration

### 4. Dry-Run Mode

#### Testing without LLM calls

Use dry-run mode to test EWS connectivity and normalization:

```bash
# Test dry-run mode
python3 -m digest_core.cli --dry-run

# Expected output: "Dry-run mode: ingest+normalize only"
# Should fail with configuration error (expected without real credentials)
```

### 5. Docker Issues

#### Error: "Address already in use"

**Cause**: Ports 9108 or 9109 already in use.

**Solution**:
```bash
# Check what's using the ports
lsof -i :9108
lsof -i :9109

# Kill existing processes or use different ports
docker run -p 9109:9109 -p 9108:9108 ...
```

#### Error: "Permission denied" on volume mounts

**Cause**: Incorrect file permissions.

**Solution**:
```bash
# Fix directory permissions
sudo mkdir -p /opt/digest/out /opt/digest/.state
sudo chown -R 1001:1001 /opt/digest/
sudo chmod -R 755 /opt/digest/
```

### 6. Test Issues

#### Error: "ModuleNotFoundError: No module named 'digest_core'"

**Cause**: PYTHONPATH not set correctly.

**Solution**:
```bash
# Set PYTHONPATH before running
export PYTHONPATH=/path/to/digest-core/src
python3 -m digest_core.cli --help

# Or run from project root
cd /path/to/digest-core
PYTHONPATH=src python3 -m digest_core.cli --help
```

### 7. Logging and Debugging

#### Enable debug logging

```bash
# Set log level to DEBUG
export DIGEST_LOG_LEVEL=DEBUG
python3 -m digest_core.cli --dry-run
```

#### Check Prometheus metrics

```bash
# Access metrics endpoint
curl http://localhost:9108/metrics

# Check specific metrics
curl http://localhost:9108/metrics | grep digest_
```

#### Health check endpoints

```bash
# Check health
curl http://localhost:9109/healthz

# Check readiness
curl http://localhost:9109/readyz
```

### 8. Performance Issues

#### High memory usage

**Cause**: Large email volumes or inefficient processing.

**Solution**:
- Reduce `lookback_hours` in config
- Increase `page_size` for EWS pagination
- Monitor memory usage with `htop` or `docker stats`

#### Slow processing

**Cause**: Network latency or LLM Gateway delays.

**Solution**:
- Check network connectivity to EWS and LLM Gateway
- Monitor LLM Gateway response times
- Consider increasing timeouts in config

### 9. Permission Issues

#### Error: "Permission denied" when creating directories

**Cause**: Insufficient permissions to create directories in system locations like `/tmp/` or `/opt/`.

**Solution**:
```bash
# Use home directory instead of system directories
export OUT_DIR="$HOME/.digest-out"
export STATE_DIR="$HOME/.digest-state"

# Or run with custom paths
cd digest-core && python -m digest_core.cli run
```

#### Error: "Cannot access /etc/ssl/corp-ca.pem"

**Cause**: No read permissions for system CA certificate.

**Solution**:
```bash
# Copy CA certificate to home directory
mkdir -p ~/.ssl
cp /etc/ssl/corp-ca.pem ~/.ssl/corp-ca.pem

# Or place in project directory
mkdir -p ./certs
cp /etc/ssl/corp-ca.pem ./certs/corp-ca.pem
```

#### Error: "Cannot write to /tmp/"

**Cause**: `/tmp/` directory is not writable or has restrictions.

**Solution**:
```bash
# Use home directory for temporary files
export TMPDIR="$HOME/.digest-temp"
mkdir -p "$TMPDIR"

# Or use project directory
export TMPDIR="./temp"
mkdir -p "$TMPDIR"
```

#### Corporate laptop restrictions

**Common issues on corporate laptops**:
- No write access to `/tmp/`
- No read access to `/etc/ssl/`
- No access to `/opt/`
- Restricted environment variables

**Workaround**:
```bash
# Set all paths to home directory
export OUT_DIR="$HOME/.digest-out"
export STATE_DIR="$HOME/.digest-state"
export TMPDIR="$HOME/.digest-temp"

# Create directories
mkdir -p "$OUT_DIR" "$STATE_DIR" "$TMPDIR"

# Run with home directory paths
cd digest-core && python -m digest_core.cli run
```

### 10. Corporate Laptop Specific Issues

#### Overview

Корпоративные ноутбуки часто имеют специфичные ограничения безопасности. См. детальный гайд: **[Corporate Laptop Setup Guide](../testing/examples/corporate_laptop_setup.md)**

#### Quick Fixes

**Проблема: Permission Denied в системных директориях**
```bash
# Используйте только домашнюю директорию
export OUT_DIR="$HOME/.digest-out"
export STATE_DIR="$HOME/.digest-state"
export TMPDIR="$HOME/.digest-temp"
mkdir -p "$OUT_DIR" "$STATE_DIR" "$TMPDIR"
```

**Проблема: Корпоративный CA сертификат**
```bash
# Получите корпоративный CA у IT
mkdir -p ~/ActionPulse/certs
cp corporate-ca.pem ~/ActionPulse/certs/

# В config.yaml:
# ews:
#   verify_ca: "$HOME/ActionPulse/certs/corporate-ca.pem"
```

**Проблема: Корпоративный прокси**
```bash
export http_proxy="http://proxy.company.com:8080"
export https_proxy="http://proxy.company.com:8080"
export no_proxy="localhost,127.0.0.1"

git config --global http.proxy http://proxy.company.com:8080
```

**Проблема: Windows/WSL**
```bash
# Используйте WSL2 вместо нативного Windows
wsl --install  # Требуется admin права один раз
wsl
cd /mnt/c/Users/YourName/ActionPulse
```

### 11. Getting Help

#### Quick Diagnostics

Запустите диагностику окружения:

```bash
cd digest-core

# Основная диагностика — проверяет config, env vars, сетевую доступность
python -m digest_core.cli diagnose

# Дополнительно — печать несекретных переменных
scripts/print_env.sh
```

**Вывод `diagnose` покажет:**
- ✓/✗ Required env vars (EWS_*, LLM_*, MM_WEBHOOK_URL)
- ✓/✗ Config file load + validation
- ✓/✗ Output / state directory writability
- ✓/✗ Network reachability к EWS и LLM Gateway endpoint'ам

#### Collect logs

```bash
cd digest-core

# Автоматический сбор всей диагностики (логи, метрики, конфиг без секретов)
scripts/collect_diagnostics.sh

# Или вручную с verbose logging
DIGEST_LOG_LEVEL=DEBUG python -m digest_core.cli run --dry-run 2>&1 | tee debug.log

# Check structured logs
cat debug.log | jq .
```

#### Report issues

**Для тестирования:** см. [`docs/testing/MANUAL_TESTING_CHECKLIST.md`](../testing/MANUAL_TESTING_CHECKLIST.md) и [`docs/testing/SEND_RESULTS.md`](../testing/SEND_RESULTS.md).

**Для разработчиков:** Включите в issue:
1. Output of `python -m digest_core.cli diagnose`
2. Архив диагностики (`scripts/collect_diagnostics.sh` → `diagnostics-*.tar.gz`)
3. Configuration (without secrets)
4. Error messages and stack traces
5. Steps to reproduce
6. OS and environment details
