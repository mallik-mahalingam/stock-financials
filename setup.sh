#!/usr/bin/env bash
# One-time setup for stock-financials (non-technical friendly).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${HOME}/.stock-financials.env"
SHELL_RC="${HOME}/.zshrc"

echo ""
echo "=========================================="
echo "  Stock Financials — one-time setup"
echo "=========================================="
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed."
  echo "Install it from https://www.python.org/downloads/ then run Setup again."
  exit 1
fi

PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Python ${PY_VER} — OK"
echo ""

if ! python3 -c "import yfinance" >/dev/null 2>&1; then
  echo "Installing yfinance (Yahoo Finance stock snapshots)..."
  python3 -m pip install --user yfinance >/dev/null 2>&1 || python3 -m pip install yfinance >/dev/null 2>&1 || true
  if python3 -c "import yfinance" >/dev/null 2>&1; then
    echo "yfinance — OK"
  else
    echo "Could not install yfinance automatically. Run: pip install yfinance"
  fi
  echo ""
fi

if [[ -f "${ENV_FILE}" ]]; then
  echo "Setup was already done (${ENV_FILE})."
  read -r -p "Update your name/email? [y/N] " AGAIN
  if [[ ! "${AGAIN}" =~ ^[Yy]$ ]]; then
    echo "Nothing changed."
    exit 0
  fi
  echo ""
fi

read -r -p "Your name (for SEC): " USER_NAME
read -r -p "Your email (for SEC): " USER_EMAIL

USER_NAME="$(echo "${USER_NAME}" | xargs)"
USER_EMAIL="$(echo "${USER_EMAIL}" | xargs)"

if [[ -z "${USER_NAME}" || -z "${USER_EMAIL}" ]]; then
  echo "Name and email are required."
  exit 1
fi

UA="SEC_USER_AGENT=\"${USER_NAME} stock-financials research ${USER_EMAIL}\""

cat > "${ENV_FILE}" <<EOF
# Created by stock-financials setup — do not commit this file.
export ${UA}
export STOCK_FINANCIALS_REPO="${REPO_ROOT}"
EOF

SOURCE_LINE='source "${HOME}/.stock-financials.env"'
if [[ -f "${SHELL_RC}" ]] && grep -Fq ".stock-financials.env" "${SHELL_RC}"; then
  echo "Shell profile already loads ${ENV_FILE}"
else
  {
    echo ""
    echo "# stock-financials"
    echo "${SOURCE_LINE}"
  } >> "${SHELL_RC}"
  echo "Added setup to ${SHELL_RC}"
fi

# Load for this session
# shellcheck disable=SC1090
source "${ENV_FILE}"

read -r -p "Link AI skill for Cursor? (add skills/ manually for Claude) [Y/n] " LINK_SKILL
if [[ ! "${LINK_SKILL}" =~ ^[Nn]$ ]]; then
  mkdir -p "${HOME}/.cursor/skills"
  ln -sf "${REPO_ROOT}/skills" "${HOME}/.cursor/skills/stock-financials"
  echo "Cursor skill linked."
fi

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "Next: ask your AI assistant — \"Get financials for AAPL\""
echo "  (Cursor, Claude Code, or double-click Get Financials.command)"
echo ""
