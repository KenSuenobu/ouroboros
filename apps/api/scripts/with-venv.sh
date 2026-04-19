#!/usr/bin/env bash
# Ensure apps/api has a Python venv with `uv` installed, then exec the given command
# inside the activated venv. Idempotent — re-running is fast (a few stat() calls).
#
# Usage:
#   ./scripts/with-venv.sh uv run uvicorn ouroboros_api.main:app --reload
#   ./scripts/with-venv.sh uv run pytest -q

set -euo pipefail

API_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${API_DIR}/.venv"
SENTINEL="${VENV_DIR}/.ouroboros-bootstrap-ok"

PYTHON_BIN="${OUROBOROS_PYTHON:-python3}"

log() {
  printf '\033[2m[api/bootstrap]\033[0m %s\n' "$*" >&2
}

if [[ ! -d "${VENV_DIR}" ]]; then
  log "creating .venv with ${PYTHON_BIN}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

if ! command -v uv >/dev/null 2>&1; then
  log "installing uv into .venv"
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet uv
fi

# Sync once per dependency-change. We track the mtime of pyproject.toml +
# uv.lock against a sentinel so we don't pay the cost on every invocation.
PYPROJECT="${API_DIR}/pyproject.toml"
LOCKFILE="${API_DIR}/uv.lock"
need_sync=0
if [[ ! -f "${SENTINEL}" ]]; then
  need_sync=1
elif [[ "${PYPROJECT}" -nt "${SENTINEL}" ]]; then
  need_sync=1
elif [[ -f "${LOCKFILE}" && "${LOCKFILE}" -nt "${SENTINEL}" ]]; then
  need_sync=1
fi

if [[ "${need_sync}" -eq 1 ]]; then
  log "running uv sync --extra dev"
  (cd "${API_DIR}" && uv sync --extra dev)
  touch "${SENTINEL}"
fi

cd "${API_DIR}"
exec "$@"
