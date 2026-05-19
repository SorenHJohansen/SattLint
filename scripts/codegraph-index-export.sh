#!/usr/bin/env bash
set -euo pipefail

# Run on the GPU PC to index and export the CodeGraph database.
# Usage: ./scripts/codegraph-index-export.sh [--project-dir .] [--languages python]

PROJECT_DIR="${1:-.}"
LANGUAGES="${2:-python}"
EXPORT_FILE="codegraph-index.surql"

echo "=== Step 1: Ensure SurrealDB is running ==="
if ! curl -s http://localhost:3004/health > /dev/null 2>&1; then
  echo "ERROR: SurrealDB is not running. Start it with:"
  echo "  surreal start --bind 0.0.0.0:3004 --user root --pass root file://\$HOME/.codegraph/surreal.db"
  exit 1
fi

echo "=== Step 2: Index the project ==="
codegraph index "$PROJECT_DIR" --languages "$LANGUAGES" -r

echo "=== Step 3: Export database to SurrealQL ==="
surreal export \
  --conn ws://localhost:3004 \
  --user root --pass root \
  --ns ouroboros --db codegraph \
  "$EXPORT_FILE"

echo "=== Done ==="
echo "Export written to: $EXPORT_FILE"
echo ""
echo "Next: git add $EXPORT_FILE && git commit -m 'update codegraph index' && git push"
