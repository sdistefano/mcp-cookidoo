#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
FASTMCP_BIN="$REPO_ROOT/.venv/bin/fastmcp"

if [[ ! -x "$FASTMCP_BIN" ]]; then
  echo "fastmcp executable not found at $FASTMCP_BIN" >&2
  echo "Create the virtual environment and install dependencies before running this script." >&2
  exit 1
fi

exec "$FASTMCP_BIN" run "$REPO_ROOT/server.py" -t streamable-http --port 9070 "$@" --host 0.0.0.0
