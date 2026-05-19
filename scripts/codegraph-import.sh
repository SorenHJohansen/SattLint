#!/usr/bin/env bash
set -euo pipefail

# Run on the dev PC after pulling a new codegraph index from git.
# Usage: ./scripts/codegraph-import.sh [--export-file codegraph-index.surql]

EXPORT_FILE="${1:-codegraph-index.surql}"

if [ ! -f "$EXPORT_FILE" ]; then
  echo "ERROR: Export file not found: $EXPORT_FILE"
  echo "Pull the latest from git first: git pull"
  exit 1
fi

echo "=== Step 1: Ensure SurrealDB is running ==="
if ! curl -s http://localhost:3004/health > /dev/null 2>&1; then
  echo "Starting SurrealDB..."
  surreal start \
    --bind 0.0.0.0:3004 \
    --user root --pass root \
    file://$HOME/.codegraph/surreal.db &
  sleep 2
fi

echo "=== Step 2: Import database from SurrealQL ==="
surreal import \
  --conn ws://localhost:3004 \
  --user root --pass root \
  --ns ouroboros --db codegraph \
  "$EXPORT_FILE"

echo "=== Step 3: Verify import ==="
surreal sql \
  --conn ws://localhost:3004 \
  --user root --pass root \
  --ns ouroboros --db codegraph \
  --command "SELECT count() FROM nodes GROUP ALL; SELECT count() FROM chunks GROUP ALL;"

echo "=== Done ==="
echo "CodeGraph index imported. Start the MCP server with:"
echo "  codegraph start stdio --watch"
