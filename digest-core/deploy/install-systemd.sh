#!/bin/bash
# Install ActionPulse systemd user timer + service.
# Run as the target user (not root).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"

echo "Installing ActionPulse systemd units..."

# Create directories
mkdir -p "$UNIT_DIR"
mkdir -p "${HOME}/.config/actionpulse"

# Copy unit files
cp "$SCRIPT_DIR/actionpulse-digest.service" "$UNIT_DIR/actionpulse-digest@.service"
cp "$SCRIPT_DIR/actionpulse-digest.timer"   "$UNIT_DIR/actionpulse-digest.timer"

# Require env file before enabling the timer — fail fast with clear guidance
if [ ! -f "${HOME}/.config/actionpulse/env" ]; then
    cat <<EOF

⚠ ${HOME}/.config/actionpulse/env not found.

Enable the timer only after configuration exists — otherwise the first fire
will fail with missing EWS_PASSWORD / LLM_TOKEN / MM_WEBHOOK_URL.

Recommended: run the interactive wizard from the repo:

    cd "$(cd "$SCRIPT_DIR/.." && pwd)" && python -m digest_core.cli setup

Or seed the template manually (headless / CI):

    cp "$SCRIPT_DIR/env.example" "${HOME}/.config/actionpulse/env"
    chmod 600 "${HOME}/.config/actionpulse/env"
    \$EDITOR "${HOME}/.config/actionpulse/env"

Then re-run this installer.

EOF
    exit 1
fi
echo "Env file already exists, continuing."

# Reload and enable
systemctl --user daemon-reload
systemctl --user enable actionpulse-digest.timer
systemctl --user start actionpulse-digest.timer

echo ""
echo "Installed. Verify with:"
echo "  systemctl --user status actionpulse-digest.timer"
echo "  systemctl --user list-timers"
echo ""
echo "Manual test run:"
echo "  systemctl --user start actionpulse-digest@\$(whoami).service"
echo ""
echo "View logs:"
echo "  journalctl --user -u actionpulse-digest@\$(whoami) -f"
