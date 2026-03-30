#!/bin/bash
set -euo pipefail

# ActionPulse Quick Installer (Non-Interactive)
# Usage: curl -fsSL https://raw.githubusercontent.com/ruspg/ActionPulse/main/digest-core/scripts/quick-install.sh | bash

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_header() { echo -e "${PURPLE}$1${NC}"; }
print_step() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

# Configuration
REPO_URL="https://github.com/ruspg/ActionPulse.git"
INSTALL_DIR="$HOME/ActionPulse"

print_header "🚀 ActionPulse Quick Installer"
echo "=================================="

# Clone repository
print_step "Cloning Repository"
if [[ -d "$INSTALL_DIR" ]]; then
    print_info "Directory exists, updating..."
    cd "$INSTALL_DIR" && git pull
else
    print_info "Cloning to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install dependencies
print_step "Installing Dependencies"
cd digest-core

if command -v uv >/dev/null 2>&1; then
    print_info "Installing with uv..."
    uv sync
elif command -v pip >/dev/null 2>&1; then
    print_info "Installing with pip..."
    pip install -e .
else
    print_info "No package manager found, skipping Python deps"
fi

cd ..

# Create working .env and config.yaml from the repo examples
print_step "Creating .env and config.yaml"
cp digest-core/.env.example digest-core/.env
cp digest-core/configs/config.example.yaml digest-core/configs/config.yaml

print_success "Quick installation complete!"

echo
print_header "Next Steps:"
echo "1. cd $INSTALL_DIR"
echo "2. Edit digest-core/.env and digest-core/configs/config.yaml (EWS_PASSWORD, LLM_TOKEN, MM_WEBHOOK_URL)"
echo "3. cd digest-core"
echo "4. Activate venv (if created) and run dry-run:"
echo "   source .venv/bin/activate 2>/dev/null || true"
echo "   python -m digest_core.cli run --dry-run"
echo "5. Optional: verify Mattermost webhook connectivity (sends one test message):"
echo "   source .env && curl -s -X POST -H 'Content-Type: application/json' -d '{\"text\":\"ActionPulse webhook ping\"}' \"\$MM_WEBHOOK_URL\" > /dev/null"
echo
print_info "For interactive setup, run: ./setup.sh"
print_info "For full documentation, see: README.md"
