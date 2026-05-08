#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "$repo_root/.venv/bin/python" ]]; then
	cd "$repo_root"
	exec "$repo_root/.venv/bin/python" "$@"
fi

if [[ -x "$repo_root/.venv/Scripts/python.exe" ]]; then
	cd "$repo_root"
	exec "$repo_root/.venv/Scripts/python.exe" "$@"
fi

cd "$repo_root"
exec python "$@"
