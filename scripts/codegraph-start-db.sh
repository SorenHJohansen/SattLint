#!/usr/bin/env bash
set -euo pipefail

# Start SurrealDB for CodeGraph with persistent file storage.
# Run this before using any codegraph commands.
# Required environment variables:
#   CODEGRAPH_SURREAL_USER
#   CODEGRAPH_SURREAL_PASS
# Optional environment variables:
#   CODEGRAPH_DB_DIR       default: $HOME/.codegraph
#   CODEGRAPH_SURREAL_BIND default: 127.0.0.1:3004

CODEGRAPH_DB_DIR="${CODEGRAPH_DB_DIR:-$HOME/.codegraph}"
CODEGRAPH_SURREAL_BIND="${CODEGRAPH_SURREAL_BIND:-127.0.0.1:3004}"
CODEGRAPH_SURREAL_USER="${CODEGRAPH_SURREAL_USER:-}"
CODEGRAPH_SURREAL_PASS="${CODEGRAPH_SURREAL_PASS:-}"

if [ -z "$CODEGRAPH_SURREAL_USER" ] || [ -z "$CODEGRAPH_SURREAL_PASS" ]; then
  echo "ERROR: Set CODEGRAPH_SURREAL_USER and CODEGRAPH_SURREAL_PASS before starting SurrealDB." >&2
  echo "The default bind is loopback-only at $CODEGRAPH_SURREAL_BIND." >&2
  exit 1
fi

mkdir -p "$CODEGRAPH_DB_DIR"

echo "Starting SurrealDB (file://$CODEGRAPH_DB_DIR/surreal.db) on $CODEGRAPH_SURREAL_BIND..."
surreal start \
  --bind "$CODEGRAPH_SURREAL_BIND" \
  --user "$CODEGRAPH_SURREAL_USER" \
  --pass "$CODEGRAPH_SURREAL_PASS" \
  "file://$CODEGRAPH_DB_DIR/surreal.db"
