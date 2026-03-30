#!/bin/bash
# Test run script with automatic diagnostics collection
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
OUT_DIR="${OUT_DIR:-${HOME}/.digest-out}"
STATE_DIR="${STATE_DIR:-${HOME}/.digest-state}"
LOG_LEVEL="${LOG_LEVEL:-DEBUG}"
COLLECT_LOGS="${COLLECT_LOGS:-true}"

echo "ActionPulse Test Run"
echo "=================="
echo "Output directory: $OUT_DIR"
echo "State directory: $STATE_DIR"
echo "Log level: $LOG_LEVEL"
echo "Auto-collect logs: $COLLECT_LOGS"
echo ""

# Create directories
mkdir -p "$OUT_DIR" "$STATE_DIR"

# Change to project root
cd "$PROJECT_ROOT"

# Function to cleanup on exit
cleanup() {
    local exit_code=$?
    echo ""
    echo "Test run completed with exit code: $exit_code"
    
    if [ "$COLLECT_LOGS" = "true" ]; then
        echo "Collecting diagnostics..."
        "$SCRIPT_DIR/collect_diagnostics.sh"
    fi
    
    exit $exit_code
}

# Set trap for cleanup
trap cleanup EXIT

# Check if required environment variables are set
echo "Checking environment variables..."
missing_vars=()

if [ -z "${EWS_PASSWORD:-}" ]; then
    missing_vars+=("EWS_PASSWORD")
fi

if [ -z "${EWS_USER_UPN:-}" ]; then
    missing_vars+=("EWS_USER_UPN")
fi

if [ -z "${LLM_TOKEN:-}" ]; then
    missing_vars+=("LLM_TOKEN")
fi

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "Warning: Missing environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "You can set them with:"
    for var in "${missing_vars[@]}"; do
        echo "  export $var=\"your_value\""
    done
    echo ""
    echo "Continuing with dry-run mode..."
    DRY_RUN=true
else
    echo "✓ All required environment variables are set"
    DRY_RUN=false
fi

# Run environment diagnostics first
echo "Running environment diagnostics..."
"$SCRIPT_DIR/print_env.sh"

echo ""
echo "Starting test run..."

# Set log level
export DIGEST_LOG_LEVEL="$LOG_LEVEL"

# Run the digest (ensure src on PYTHONPATH if not installed)
export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH:-}"
if [ "$DRY_RUN" = "true" ]; then
    echo "Running in dry-run mode (no LLM calls)..."
python3 -m digest_core.cli run \
        --dry-run \
        --out "$OUT_DIR" \
        --state "$STATE_DIR" \
        --window calendar_day \
        --model "qwen3.5-397b-a17b"
else
    echo "Running full digest generation..."
    python3 -m digest_core.cli run \
        --out "$OUT_DIR" \
        --state "$STATE_DIR" \
        --window calendar_day \
        --model "qwen3.5-397b-a17b"
fi

echo ""
echo "Test run completed successfully!"
echo "Check output files in: $OUT_DIR"

# List output files
if [ -d "$OUT_DIR" ]; then
    echo ""
    echo "Generated files:"
    find "$OUT_DIR" -type f -exec ls -lh {} \; | while read -r line; do
        echo "  $line"
    done
fi
