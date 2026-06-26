#!/usr/bin/env bash
# Download SEC financials and build the Cursor canvas for one ticker.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${HOME}/.stock-financials.env"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
elif [[ -z "${SEC_USER_AGENT:-}" ]]; then
  echo ""
  echo "Setup is not done yet."
  echo "Double-click \"Setup.command\" first."
  echo ""
  exit 1
fi

TICKER="${1:-}"
if [[ -z "${TICKER}" ]]; then
  echo ""
  read -r -p "Stock ticker (example: AAPL, PANW, MSFT): " TICKER
fi

TICKER="$(echo "${TICKER}" | tr '[:lower:]' '[:upper:]' | xargs)"
if [[ -z "${TICKER}" ]]; then
  echo "No ticker entered."
  exit 1
fi

echo ""
echo "Fetching 12 quarters for ${TICKER} from SEC..."
echo "(First time may take about a minute.)"
echo ""

python3 "${REPO_ROOT}/scripts/sec_financials.py" sync "${TICKER}"

CANVAS="${REPO_ROOT}/canvas/$(echo "${TICKER}" | tr '[:upper:]' '[:lower:]')-financials.canvas.tsx"

echo ""
echo "=========================================="
echo "  Done — ${TICKER}"
echo "=========================================="
echo ""
echo "Open this file in Cursor:"
echo "  ${CANVAS}"
echo ""

if command -v cursor >/dev/null 2>&1; then
  cursor "${CANVAS}" 2>/dev/null || true
elif [[ "$(uname)" == "Darwin" ]]; then
  open -R "${CANVAS}" 2>/dev/null || true
  echo "(File highlighted in Finder — drag it into Cursor, or open from Cursor's file tree.)"
fi

echo ""
