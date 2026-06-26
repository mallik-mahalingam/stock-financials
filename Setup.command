#!/bin/bash
cd "$(dirname "$0")"
chmod +x setup.sh get-financials.sh 2>/dev/null || true
./setup.sh
echo ""
read -n 1 -s -r -p "Press any key to close this window..."
echo ""
