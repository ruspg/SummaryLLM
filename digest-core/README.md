# digest-core

Daily corporate communications digest with LLM-powered action extraction.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Virtual Environment](#virtual-environment)
- [Quick Start](#quick-start)
- [Manual Installation](#manual-installation)
- [Troubleshooting Installation](#troubleshooting-installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Development](#development)
- [Architecture](#architecture)
- [Idempotency](#idempotency)
- [Security](#security)
- [Documentation Links](#documentation-links)

## Features

- **EWS Integration**: NTLM authentication, corporate CA trust, incremental sync
- **Idempotent**: T-48h rebuild window for deterministic results
- **Dry-Run Mode**: Test EWS connectivity and normalization without LLM calls
- **Observability**: Prometheus metrics (:9108), health checks (:9109), structured JSON logs
- **Schema Validation**: Strict Pydantic validation for all outputs

## Requirements

- Python 3.11+ (на macOS: `brew install python@3.11`, запуск: `python3.11 -m digest_core.cli ...`)
- Access to Exchange Web Services (EWS)
- LLM Gateway endpoint

## Virtual Environment

The installation script automatically creates a virtual environment in `.venv/`. This provides:
- **Isolation**: Dependencies don't conflict with system Python
- **Consistency**: Same environment across all installations
- **Simplicity**: No need to manage `uv` or other tools

**Usage**:
```bash
# Activate venv (recommended)
source .venv/bin/activate
python -m digest_core.cli run

# Or use directly without activation
.venv/bin/python -m digest_core.cli run
```

**The `py.sh` helper script** automatically uses `.venv` if it exists:
```bash
digest-core/scripts/py.sh -m digest_core.cli run
```

## Quick Start

### One-Command Install (new users)

```bash
curl -fsSL https://raw.githubusercontent.com/ruspg/ActionPulse/main/digest-core/scripts/install.sh | bash
```

This clones the repo, installs dependencies, and runs the interactive setup wizard.

### From existing clone

```bash
# From ActionPulse root directory
./digest-core/scripts/setup.sh

# Or from digest-core/
make setup-wizard
```

This will guide you through all configuration steps and generate the necessary files.

### After Setup

The setup script automatically creates a virtual environment in `.venv`.

1. **Activate virtual environment**:
   ```bash
   source .venv/bin/activate
   ```

2. **Load environment variables**:
   ```bash
   set -a && source ../.env && set +a
   ```

3. **Check configuration**:
   ```bash
   make env-check
   ```

4. **Run first digest**:
   ```bash
   # Test run (without LLM)
   python -m digest_core.cli run --dry-run
   
   # Full run for today
   python -m digest_core.cli run
   ```

**Alternative**: Run without activating venv:
```bash
set -a && source ../.env && set +a
.venv/bin/python -m digest_core.cli run --dry-run
```

## Manual Installation

If you're not using the automated setup script:

```bash
cd digest-core

# Create virtual environment
python3.11 -m venv .venv

# Activate it
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -e .

# Or use make (which will use venv if it exists)
make setup
```

## Deployment & Infrastructure

For detailed deployment instructions, see:
- **[DEPLOYMENT.md](../docs/operations/DEPLOYMENT.md)** - Docker setup, dedicated machine configuration, infrastructure requirements
- **[AUTOMATION.md](../docs/operations/AUTOMATION.md)** - Scheduling with systemd/cron, state management, advanced automation
- **[MONITORING.md](../docs/operations/MONITORING.md)** - Prometheus metrics, health checks, logging, observability

## Troubleshooting Installation

### TLS/SSL Certificate Errors

If you encounter `invalid peer certificate: UnknownIssuer` during installation:

```bash
# Use trusted-host to bypass corporate certificate issues
cd digest-core
source .venv/bin/activate
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .
```

### Missing venv

If the virtual environment wasn't created:

```bash
# Run the diagnostic script
../digest-core/scripts/fix_installation.sh

# Or create manually
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### Outdated Configuration

If you get `Cannot determine NTLM username` error:

```bash
# Update repository
cd ..
git pull

# Recreate configuration
./digest-core/scripts/setup.sh
```

### Manual Dependency Installation

If all else fails:

```bash
# Navigate to digest-core
cd digest-core

# Activate venv
source .venv/bin/activate

# Install with corporate certificate workaround
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --upgrade pip
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .
```

## Configuration

1. Copy example configuration:
```bash
cp configs/config.example.yaml configs/config.yaml
```

2. Set environment variables:
```bash
export EWS_PASSWORD="your_ews_password"
export EWS_USER_UPN="user@corp.com"
export EWS_USER_LOGIN="user"
export EWS_USER_DOMAIN="corp.com"
export EWS_ENDPOINT="https://ews.corp.com/EWS/Exchange.asmx"
export LLM_TOKEN="your_llm_token"
export LLM_ENDPOINT="https://llm-gw.corp.com/api/v1/chat"
export MM_WEBHOOK_URL="https://mm.corp.com/hooks/xxx"  # optional
```

Or create `.env` file with these variables (the setup wizard generates it automatically).

3. Update `configs/config.yaml` with your settings:
   - EWS endpoint and credentials
   - LLM Gateway endpoint and model
   - Timezone and time window preferences

## Usage

### CLI Examples

#### Basic Commands

```bash
# Run digest for today
python3.11 -m digest_core.cli run

# Run for specific date
python3.11 -m digest_core.cli run --from-date 2024-01-15

# Custom output directory
python3.11 -m digest_core.cli run --out ./my-digests

# Dry-run mode (ingest+normalize only, no LLM calls)
python3.11 -m digest_core.cli run --dry-run

# Using make
make run
```

#### Advanced Options

```bash
# Different time window (rolling 24h instead of calendar day)
python3.11 -m digest_core.cli run --window rolling_24h

# Custom LLM model
python3.11 -m digest_core.cli run --model "qwen35-397b-a17b"

# Multiple sources (if implemented)
python3.11 -m digest_core.cli run --sources "ews,mattermost"

# Force rebuild (ignore idempotency)
python3.11 -m digest_core.cli run --force

# Verbose output
python3.11 -m digest_core.cli run --verbose
```

#### Common Scenarios

**Daily Automated Run:**
```bash
# Add to crontab for daily 8 AM execution
0 8 * * * cd /path/to/digest-core && set -a && source ../.env && set +a && .venv/bin/python -m digest_core.cli run
```

**Historical Digest Generation:**
```bash
# Generate digests for the past week
for date in $(seq -f "2024-01-%02g" 8 14); do
    python3.11 -m digest_core.cli run --from-date $date
done
```

**Testing Configuration:**
```bash
# Test EWS connectivity without LLM
python3.11 -m digest_core.cli run --dry-run

# Test with different model
python3.11 -m digest_core.cli run --model "qwen35-397b-a17b" --dry-run
```

**Multiple Mailboxes (if configured):**
```bash
# Process different mailboxes by updating config.yaml folders
python3.11 -m digest_core.cli run --from-date 2024-01-15
```

### Output Files

#### JSON Structure

The `digest-YYYY-MM-DD.json` file contains structured data with the following schema:

```json
{
  "digest_date": "2024-01-15",
  "generated_at": "2024-01-15T10:30:00Z",
  "trace_id": "abc123-def456",
  "sections": [
    {
      "title": "Мои действия",
      "items": [
        {
          "title": "Утвердить лимиты Q3",
          "owners_masked": ["Иван Иванов"],
          "due": "2024-01-17",
          "evidence_id": "ev:msghash:1024:480",
          "confidence": 0.86,
          "source_ref": {
            "type": "email",
            "msg_id": "urn:ews:...",
            "conversation_id": "conv123"
          }
        }
      ]
    }
  ]
}
```

#### Markdown Format

The `digest-YYYY-MM-DD.md` file provides human-readable output:

```markdown
# Дайджест — 2024-01-15

## Мои действия
- Утвердить лимиты Q3 — до **2024-01-17**. Ответственные: Иван Иванов.  
  Источник: письмо «Q3 Budget plan», evidence ev:msghash:1024:480.

## Срочно
- Петр Петров просит подтвердить SLA инцидента #7842.  
  Источник: «ADP incident update», evidence ev:...
```

#### Evidence References

Each item includes:
- `evidence_id`: Reference to source evidence fragment
- `source_ref`: Message metadata (type, msg_id, conversation_id)
- `confidence`: Extraction confidence score (0-1)
- `owners_masked`: Responsible parties
- `due`: Optional deadline

### Troubleshooting Quick Reference

#### Empty Digest Issues

**Problem**: Digest is empty despite having emails
```bash
# Check time window settings
grep -A 5 "time:" configs/config.yaml

# Verify lookback hours
grep "lookback_hours" configs/config.yaml

# Test with dry-run to see ingested emails
python -m digest_core.cli run --dry-run
```

**Solutions**:
- Adjust `lookback_hours` in config.yaml
- Change `window` from `calendar_day` to `rolling_24h`
- Check EWS folder permissions

#### Connection Errors

**Problem**: EWS endpoint not reachable
```bash
# Test connectivity
curl -I https://your-ews-endpoint.com/EWS/Exchange.asmx

# Check certificate
openssl s_client -connect your-ews-endpoint.com:443

# Verify CA certificate path
ls -la /etc/ssl/corp-ca.pem
```

**Solutions**:
- Verify EWS endpoint URL
- Check corporate CA certificate
- Test network connectivity
- Verify firewall settings

#### Authentication Issues

**Problem**: EWS authentication fails
```bash
# Check environment variables
echo $EWS_PASSWORD
echo $EWS_USER_UPN

# Test with dry-run
python -m digest_core.cli run --dry-run
```

**Solutions**:
- Verify UPN format (user@domain.com)
- Check password validity
- Ensure account has EWS permissions
- Test with Outlook Web Access

#### Configuration Validation

**Problem**: Configuration errors
```bash
# Run environment check
make env-check

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('configs/config.yaml'))"

# Test configuration loading
python -c "from digest_core.config import Config; print(Config())"
```

**Solutions**:
- Fix YAML syntax errors
- Verify all required fields are present
- Check environment variable names
- Ensure proper indentation

#### LLM Gateway Issues

**Problem**: LLM requests failing
```bash
# Test LLM endpoint
curl -H "Authorization: Bearer $LLM_TOKEN" $LLM_ENDPOINT

# Check token validity
echo $LLM_TOKEN | wc -c

# Test with verbose output
python -m digest_core.cli run --verbose
```

**Solutions**:
- Verify LLM token is valid
- Check endpoint URL format
- Ensure proper headers in config
- Test with different model


## Observability

For detailed monitoring and observability setup, see **[MONITORING.md](../docs/operations/MONITORING.md)**.

Quick diagnostics:
```bash
# Run diagnostics
./digest-core/scripts/print_env.sh

# Or using make
make env-check
```

## Development

### Testing

```bash
# Run tests
make test

# Run with coverage
pytest --cov=digest_core tests/
```

### Linting

```bash
# Check code style
make lint

# Auto-format
make format
```

## Architecture

```
EWS → normalize → thread → evidence split → context select
  → LLM Gateway → validate → assemble (JSON/MD)
  → metrics + logs
```

See `docs/ARCHITECTURE.md` for detailed architecture documentation.

## Idempotency

Runs are idempotent per `(user_id, digest_date)` with a T-48h rebuild window:
- If artifacts exist and are <48h old: skip rebuild
- If artifacts are >48h old or missing: rebuild

To force rebuild, delete existing artifacts or use `--force` flag.

## Security

- **No Payload Logging**: Message bodies never logged
- **Corporate CA**: TLS verification with custom CA
- **Non-root Container**: Docker runs as UID 1001
- **Secret Management**: Credentials via ENV only

## Documentation Links

- **[📚 Full Documentation](../docs/README.md)** - Complete documentation navigation
- **[🚀 Quick Start](../docs/installation/QUICK_START.md)** - Get started in 5 minutes
- **[🔧 Installation Guide](../docs/installation/QUICK_START.md)** - Installation instructions and quick start
- **[🐳 Deployment](../docs/operations/DEPLOYMENT.md)** - Docker setup, dedicated machine configuration
- **[⏰ Automation](../docs/operations/AUTOMATION.md)** - Scheduling with systemd/cron, state management
- **[📊 Monitoring](../docs/operations/MONITORING.md)** - Prometheus metrics, health checks, observability
- **[🚨 Troubleshooting](../docs/troubleshooting/TROUBLESHOOTING.md)** - Common issues and solutions
- **[🏗️ Architecture](../docs/development/ARCHITECTURE.md)** - System architecture and components
- **[📖 Technical Details](../docs/development/TECHNICAL.md)** - Technical specifications and configuration

## License

Internal corporate use only.

