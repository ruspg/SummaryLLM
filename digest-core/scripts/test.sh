#!/bin/bash
# Test script with pytest and coverage
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Running tests with pytest..."

cd "$PROJECT_ROOT"

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "Error: pytest not found. Install with: uv add pytest pytest-cov"
    exit 1
fi

# Run tests with coverage
echo "Running tests with coverage..."
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if pytest --help 2>/dev/null | grep -q -- "--cov"; then
    pytest tests/ -v --cov=src/digest_core --cov-report=term-missing --cov-report=html
else
    echo "pytest-cov not available, running without coverage"
    pytest tests/ -v
fi

# Check if tests passed
if [ $? -eq 0 ]; then
    echo "All tests passed!"
    exit 0
else
    echo "Tests failed!"
    exit 1
fi
