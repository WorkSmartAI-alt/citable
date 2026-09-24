#!/usr/bin/env bash
# Run a citable audit from the source bundled with this plugin.
# Usage: run_audit.sh <domain-or-url> [pages] [output.xlsx]
#        run_audit.sh --summarize <report.xlsx>
set -euo pipefail

TARGET="${1:?usage: run_audit.sh <domain-or-url> [pages] [output.xlsx] | --summarize <report.xlsx>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENV="${CITABLE_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/citable-plugin/venv}"
LIB="${VENV}-lib"
DEPS=("httpx[http2]>=0.27" "beautifulsoup4>=4.12" "openpyxl>=3.1" "typer>=0.12" "rich>=13.7" "lxml>=5.0")
CHECK="import httpx, h2, bs4, openpyxl, typer, rich, lxml"

if [ ! -f "$REPO_ROOT/src/citable/cli.py" ]; then
  echo "citable source not found under $REPO_ROOT/src. Reinstall the plugin." >&2
  exit 2
fi

# Pick an interpreter that has the dependencies, installing them on first run.
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "$CHECK" >/dev/null 2>&1; then
  PY="$VENV/bin/python"
elif [ -d "$LIB" ] && PYTHONPATH="$LIB" python3 -c "$CHECK" >/dev/null 2>&1; then
  PY="python3"; export PYTHONPATH="$LIB"
else
  echo "First run: installing citable's dependencies (about a minute)..." >&2
  if python3 -m venv "$VENV" >/dev/null 2>&1; then
    "$VENV/bin/pip" install --quiet --disable-pip-version-check "${DEPS[@]}"
    PY="$VENV/bin/python"
  else
    # No venv module here: install into a private folder instead.
    python3 -m pip install --quiet --disable-pip-version-check --target "$LIB" "${DEPS[@]}"
    PY="python3"; export PYTHONPATH="$LIB"
  fi
fi

if [ "$TARGET" = "--summarize" ]; then
  REPORT="${2:?usage: run_audit.sh --summarize <report.xlsx>}"
  exec "$PY" "$SCRIPT_DIR/summarize_report.py" "$REPORT"
fi

PAGES="${2:-20}"
OUTPUT="${3:-}"
ARGS=(audit "$TARGET" --pages "$PAGES" --no-banner)
if [ -n "$OUTPUT" ]; then
  mkdir -p "$(dirname "$OUTPUT")"
  ARGS+=(--output "$OUTPUT")
fi

export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m citable "${ARGS[@]}"
