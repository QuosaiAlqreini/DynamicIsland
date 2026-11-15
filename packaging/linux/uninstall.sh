#!/usr/bin/env bash
# Remove Dynamic Island (your settings in ~/.dynamic_island are kept; delete that folder too if you want).
set -u
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/dynamic-island"
pkill -f "$APP_DIR/dynamic-island" 2>/dev/null || true
rm -rf "$APP_DIR" "$HOME/.local/bin/dynamic-island" \
  "${XDG_DATA_HOME:-$HOME/.local/share}/applications/dynamic-island.desktop" \
  "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps/dynamic-island.png" \
  "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/dynamic-island.desktop"
echo "✓ Dynamic Island removed"
