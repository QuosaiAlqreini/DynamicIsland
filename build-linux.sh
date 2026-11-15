#!/usr/bin/env bash
# Build Dynamic Island for Linux: a folder app + DynamicIsland-<version>-linux-x86_64.tar.gz
# with install.sh. Needs Python 3.10+. Run:  ./build-linux.sh
set -euo pipefail
cd "$(dirname "$0")"
VERSION="$(python3 -c 'from version import __version__; print(__version__)')"
echo "Building Dynamic Island $VERSION for Linux"
python3 -m pip install -q -r requirements.txt pyinstaller
rm -rf build dist installer_output
python3 -m PyInstaller --noconfirm --clean --windowed \
  --name dynamic-island \
  --add-data "assets:assets" \
  --hidden-import pynput.keyboard._xorg --hidden-import pynput.mouse._xorg \
  --collect-data tzdata \
  --exclude-module tkinter \
  app.py

# Make sure the packaged app really starts (on a virtual screen when there is none)
selftest=(dist/dynamic-island/dynamic-island --selftest)
if [[ -z "${DISPLAY:-}" ]] && command -v xvfb-run >/dev/null; then
  selftest=(xvfb-run -a -s "-screen 0 1920x1080x24" "${selftest[@]}")
fi
HOME="$(mktemp -d)" QT_QPA_PLATFORM=xcb timeout 120 "${selftest[@]}"
echo "Packaged app self-test passed"

PKG="DynamicIsland-$VERSION-linux-x86_64"
mkdir -p "installer_output/$PKG"
cp -r dist/dynamic-island "installer_output/$PKG/dynamic-island"
cp packaging/linux/install.sh packaging/linux/uninstall.sh packaging/linux/dynamic-island.desktop "installer_output/$PKG/"
cp assets/icon.png "installer_output/$PKG/dynamic-island.png"
chmod +x "installer_output/$PKG/install.sh" "installer_output/$PKG/uninstall.sh"
tar -C installer_output -czf "installer_output/$PKG.tar.gz" "$PKG"
rm -rf "installer_output/$PKG"
ls -lh installer_output
