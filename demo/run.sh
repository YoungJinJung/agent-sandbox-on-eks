#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
export PYTHONUNBUFFERED=1
exec uv run --with-requirements src/mcp_server/requirements.txt python demo/stage.py "$@"
