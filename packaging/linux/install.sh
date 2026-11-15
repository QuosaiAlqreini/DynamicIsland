#!/usr/bin/env bash
# Install Dynamic Island for this user (no sudo needed for the app itself).
#   ./install.sh              install / update
#   ./install.sh --autostart  ...and start it when you log in
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/dynamic-island"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"

pkill -f "$APP_DIR/dynamic-island" 2>/dev/null || true
mkdir -p "$APP_DIR" "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"
rm -rf "$APP_DIR"/*
cp -r "$HERE/dynamic-island/." "$APP_DIR/"
chmod +x "$APP_DIR/dynamic-island"
ln -sf "$APP_DIR/dynamic-island" "$BIN_DIR/dynamic-island"
cp "$HERE/dynamic-island.png" "$ICON_DIR/dynamic-island.png"
sed "s|@EXEC@|$APP_DIR/dynamic-island|" "$HERE/dynamic-island.desktop" > "$APPS_DIR/dynamic-island.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true

if [[ "${1:-}" == "--autostart" ]]; then
  mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
  cp "$APPS_DIR/dynamic-island.desktop" "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/dynamic-island.desktop"
  echo "✓ Starts when you log in"
fi
echo "✓ Installed. Open “Dynamic Island” from your apps menu, or run: dynamic-island"

# Helper programs that unlock more features (all optional)
missing=()
for t in playerctl xprop xdotool brightnessctl; do command -v "$t" >/dev/null || missing+=("$t"); done
command -v wpctl >/dev/null || command -v pactl >/dev/null || missing+=("pulseaudio-utils")
if (( ${#missing[@]} )); then
  pkgs="${missing[*]}"
  echo
  echo "Optional: for music, fullscreen hiding, automations and brightness, install:"
  if command -v apt >/dev/null; then echo "  sudo apt install ${pkgs/xprop/x11-utils} libxcb-cursor0"
  elif command -v dnf >/dev/null; then echo "  sudo dnf install ${pkgs/xprop/xprop} xcb-util-cursor"
  elif command -v pacman >/dev/null; then echo "  sudo pacman -S ${pkgs/xprop/xorg-xprop} xcb-util-cursor"
  else echo "  $pkgs"; fi
fi
if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
  echo
  echo "Wayland: the island runs through XWayland. If your global hotkey does not work, add a"
  echo "keyboard shortcut in your desktop settings that runs:  dynamic-island --toggle"
fi
