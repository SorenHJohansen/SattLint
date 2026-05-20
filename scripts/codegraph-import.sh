#!/usr/bin/env bash
set -euo pipefail

# Run on the dev PC after pulling a new codegraph index from git.
# Usage: ./scripts/codegraph-import.sh [--export-file codegraph-index.surql]
# Required environment variables:
#   CODEGRAPH_SURREAL_USER
#   CODEGRAPH_SURREAL_PASS
# Optional environment variables:
#   CODEGRAPH_DB_DIR            default: $HOME/.codegraph
#   CODEGRAPH_SURREAL_BIND      default: 127.0.0.1:3004
#   CODEGRAPH_SURREAL_HTTP_URL  default: http://$CODEGRAPH_SURREAL_BIND
#   CODEGRAPH_SURREAL_WS_URL    default: ws://$CODEGRAPH_SURREAL_BIND

EXPORT_FILE="${1:-codegraph-index.surql}"
CODEGRAPH_DB_DIR="${CODEGRAPH_DB_DIR:-$HOME/.codegraph}"
CODEGRAPH_SURREAL_BIND="${CODEGRAPH_SURREAL_BIND:-127.0.0.1:3004}"
CODEGRAPH_SURREAL_HTTP_URL="${CODEGRAPH_SURREAL_HTTP_URL:-http://$CODEGRAPH_SURREAL_BIND}"
CODEGRAPH_SURREAL_WS_URL="${CODEGRAPH_SURREAL_WS_URL:-ws://$CODEGRAPH_SURREAL_BIND}"
CODEGRAPH_SURREAL_NAMESPACE="${CODEGRAPH_SURREAL_NAMESPACE:-ouroboros}"
CODEGRAPH_SURREAL_DATABASE="${CODEGRAPH_SURREAL_DATABASE:-codegraph}"
CODEGRAPH_SURREAL_USER="${CODEGRAPH_SURREAL_USER:-}"
CODEGRAPH_SURREAL_PASS="${CODEGRAPH_SURREAL_PASS:-}"

if [ ! -f "$EXPORT_FILE" ]; then
  echo "ERROR: Export file not found: $EXPORT_FILE"
  echo "Pull the latest from git first: git pull"
  exit 1
fi

if [ -z "$CODEGRAPH_SURREAL_USER" ] || [ -z "$CODEGRAPH_SURREAL_PASS" ]; then
  echo "ERROR: Set CODEGRAPH_SURREAL_USER and CODEGRAPH_SURREAL_PASS before importing CodeGraph data." >&2
  echo "Use ./scripts/codegraph-start-db.sh with the same environment to start SurrealDB safely." >&2
  exit 1
fi

echo "=== Step 1: Ensure SurrealDB is running ==="
if ! curl -fsS "$CODEGRAPH_SURREAL_HTTP_URL/health" > /dev/null 2>&1; then
  mkdir -p "$CODEGRAPH_DB_DIR"
  echo "Starting SurrealDB on $CODEGRAPH_SURREAL_BIND..."
  surreal start \
    --bind "$CODEGRAPH_SURREAL_BIND" \
    --user "$CODEGRAPH_SURREAL_USER" \
    --pass "$CODEGRAPH_SURREAL_PASS" \
    "file://$CODEGRAPH_DB_DIR/surreal.db" &
  sleep 2
fi

echo "=== Step 2: Import database from SurrealQL ==="
surreal import \
  --conn "$CODEGRAPH_SURREAL_WS_URL" \
  --user "$CODEGRAPH_SURREAL_USER" \
  --pass "$CODEGRAPH_SURREAL_PASS" \
  --ns "$CODEGRAPH_SURREAL_NAMESPACE" \
  --db "$CODEGRAPH_SURREAL_DATABASE" \
  "$EXPORT_FILE"

echo "=== Step 3: Verify import ==="
surreal sql \
  --conn "$CODEGRAPH_SURREAL_WS_URL" \
  --user "$CODEGRAPH_SURREAL_USER" \
  --pass "$CODEGRAPH_SURREAL_PASS" \
  --ns "$CODEGRAPH_SURREAL_NAMESPACE" \
  --db "$CODEGRAPH_SURREAL_DATABASE" \
  --command "SELECT count() FROM nodes GROUP ALL; SELECT count() FROM chunks GROUP ALL;"

echo "=== Done ==="
echo "CodeGraph index imported. Start the MCP server with:"
echo "  codegraph start stdio --watch"
