#!/usr/bin/env bash
set -euo pipefail

# Start SurrealDB for CodeGraph with persistent file storage.
# Run this before using any codegraph commands.

DB_DIR="${CODEGRAPH_DB_DIR:-$HOME/.codegraph}"
mkdir -p "$DB_DIR"

echo "Starting SurrealDB (file://$DB_DIR/surreal.db)..."
surreal start \
  --bind 0.0.0.0:3004 \
  --user root --pass root \
  "file://$DB_DIR/surreal.db"
