#!/usr/bin/env bash
# Copy Hoops shelve settings from the original ledplay install.
# Required for load_real_settings() — *.dat files are gitignored.
#
# Usage:
#   ./scripts/setup_settings.sh
#   HOOPS_LEDPLAY=/path/to/hoops/ledplay ./scripts/setup_settings.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${HOOPS_LEDPLAY:-/Users/apple/Desktop/activerse/hoops/ledplay/setting}"
DEST="$ROOT/games/setting"

if [[ ! -d "$SRC" ]]; then
  echo "Source settings not found: $SRC" >&2
  echo "Set HOOPS_LEDPLAY to your hoops/ledplay directory." >&2
  exit 1
fi

mkdir -p "$DEST"
cp -f "$SRC"/led_parameter.* "$SRC"/debug_parameter.* "$DEST/" 2>/dev/null || true
echo "Settings copied to $DEST"
echo "Verify: python3 -c \"import shelve; d=shelve.open('$DEST/led_parameter','r'); print('game_time_sw', d.get('game_time_sw')); d.close()\""
