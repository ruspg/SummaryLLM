#!/bin/bash
# Local run script with convenient paths
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default paths
OUT_DIR="${OUT_DIR:-${HOME}/.digest-out}"
STATE_DIR="${STATE_DIR:-${HOME}/.digest-state}"

# Create directories if they don't exist
mkdir -p "$OUT_DIR" "$STATE_DIR"

echo "Running digest-core locally..."
echo "Output directory: $OUT_DIR"
echo "State directory: $STATE_DIR"

cd "$PROJECT_ROOT"

# Run the digest (ensure src on PYTHONPATH if not installed)
export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH:-}"

python3 -m digest_core.cli run \
    --out "$OUT_DIR" \
    --state "$STATE_DIR" \
    --window calendar_day \
    --model "qwen3.5-397b-a17b"

echo "Local run completed!"
echo "Check output files in: $OUT_DIR"
