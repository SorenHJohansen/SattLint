#!/usr/bin/env bash
set -euo pipefail

# Run on the GPU PC to index and export the CodeGraph database.
# Usage: ./scripts/codegraph-index-export.sh [--project-dir .] [--languages python]
# Required environment variables:
#   CODEGRAPH_SURREAL_USER
#   CODEGRAPH_SURREAL_PASS
# Optional environment variables:
#   CODEGRAPH_SURREAL_BIND      default: 127.0.0.1:3004
#   CODEGRAPH_SURREAL_HTTP_URL  default: http://$CODEGRAPH_SURREAL_BIND
#   CODEGRAPH_SURREAL_WS_URL    default: ws://$CODEGRAPH_SURREAL_BIND

PROJECT_DIR="${1:-.}"
LANGUAGES="${2:-python}"
EXPORT_FILE="codegraph-index.surql"
CODEGRAPH_SURREAL_BIND="${CODEGRAPH_SURREAL_BIND:-127.0.0.1:3004}"
CODEGRAPH_SURREAL_HTTP_URL="${CODEGRAPH_SURREAL_HTTP_URL:-http://$CODEGRAPH_SURREAL_BIND}"
CODEGRAPH_SURREAL_WS_URL="${CODEGRAPH_SURREAL_WS_URL:-ws://$CODEGRAPH_SURREAL_BIND}"
CODEGRAPH_SURREAL_NAMESPACE="${CODEGRAPH_SURREAL_NAMESPACE:-ouroboros}"
CODEGRAPH_SURREAL_DATABASE="${CODEGRAPH_SURREAL_DATABASE:-codegraph}"
CODEGRAPH_SURREAL_USER="${CODEGRAPH_SURREAL_USER:-}"
CODEGRAPH_SURREAL_PASS="${CODEGRAPH_SURREAL_PASS:-}"

if [ -z "$CODEGRAPH_SURREAL_USER" ] || [ -z "$CODEGRAPH_SURREAL_PASS" ]; then
  echo "ERROR: Set CODEGRAPH_SURREAL_USER and CODEGRAPH_SURREAL_PASS before exporting CodeGraph data." >&2
  echo "Use ./scripts/codegraph-start-db.sh with the same environment to start SurrealDB safely." >&2
  exit 1
fi

echo "=== Step 1: Ensure SurrealDB is running ==="
if ! curl -fsS "$CODEGRAPH_SURREAL_HTTP_URL/health" > /dev/null 2>&1; then
  echo "ERROR: SurrealDB is not running. Start it with:"
  echo "  CODEGRAPH_SURREAL_USER=... CODEGRAPH_SURREAL_PASS=... ./scripts/codegraph-start-db.sh"
  exit 1
fi

echo "=== Step 2: Index the project ==="
codegraph index "$PROJECT_DIR" --languages "$LANGUAGES" -r

echo "=== Step 3: Export database to SurrealQL ==="
surreal export \
  --conn "$CODEGRAPH_SURREAL_WS_URL" \
  --user "$CODEGRAPH_SURREAL_USER" \
  --pass "$CODEGRAPH_SURREAL_PASS" \
  --ns "$CODEGRAPH_SURREAL_NAMESPACE" \
  --db "$CODEGRAPH_SURREAL_DATABASE" \
  "$EXPORT_FILE"

echo "=== Done ==="
echo "Export written to: $EXPORT_FILE"
echo ""
echo "Next: git add $EXPORT_FILE && git commit -m 'update codegraph index' && git push"
