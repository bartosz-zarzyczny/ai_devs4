#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/run_railway.sh YOUR_API_KEY
# Optional env:
#   PORT=8000

API_KEY="${1:-${AI_DEVS_4_API_KEY:-}}"
if [[ -z "$API_KEY" ]]; then
  echo "Brak API key. Podaj jako argument lub ustaw AI_DEVS_4_API_KEY." >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT_DIR/../.venv/Scripts/python.exe"
LOG_FILE="$ROOT_DIR/logs/railway_requests.log"

"$PY" -m pip install -r "$ROOT_DIR/requirements.txt"
"$PY" "$ROOT_DIR/scripts/railway_client.py" --apikey "$API_KEY" --auto --route x-01 --log "$LOG_FILE"

grep -E "FLG|COUNTRYROADS" "$LOG_FILE" || true

echo
echo "Aby uruchomic UI logow:"
echo "  $PY $ROOT_DIR/scripts/serve_ui.py --port ${PORT:-8000}"
echo "  http://localhost:${PORT:-8000}/ui/"
