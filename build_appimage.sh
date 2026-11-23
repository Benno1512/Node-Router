#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
#
# Builds Node-Router-<version>-x86_64.AppImage – a single executable file
# with Python, PySide6, Qt and the effect plugins. PipeWire tools (pw-dump,
# pw-link, pactl, pipewire) still come from the system.
#
#   ./build_appimage.sh            result: build/Node-Router-<version>-x86_64.AppImage
#
# Downloads on the first run: PySide6 + PyInstaller (PyPI) into build/venv and
# appimagetool (github.com/AppImage/appimagetool) into build/tools.
# Note: the AppImage runs on systems with at least the glibc version of the
# build machine (built here on Ubuntu 24.04 → glibc 2.39).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
B="$DIR/build"
APP=node-router
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$DIR/main.py")"
OUT="$B/Node-Router-$VERSION-x86_64.AppImage"
TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
mkdir -p "$B/tools"

echo "== Build environment ($B/venv)"
if [ ! -x "$B/venv/bin/python" ]; then python3 -m venv "$B/venv"; fi
"$B/venv/bin/python" -m pip install --quiet --upgrade pip
"$B/venv/bin/python" -m pip install --quiet -r "$DIR/requirements.txt" "pyinstaller>=6,<7"
"$B/venv/bin/python" -c 'import PySide6, PyInstaller; print("  PySide6", PySide6.__version__, "· PyInstaller", PyInstaller.__version__)'

echo "== Bundling (PyInstaller)"
rm -rf "$B/work" "$B/dist" "$B/AppDir"
"$B/venv/bin/pyinstaller" --noconfirm --clean --onedir --name "$APP" \
  --distpath "$B/dist" --workpath "$B/work" --specpath "$B" \
  --add-data "$DIR/icon.svg:." \
  --add-data "$DIR/plugins:plugins" \
  --exclude-module tkinter --exclude-module unittest \
  "$DIR/main.py" >"$B/pyinstaller.log" 2>&1 || { tail -30 "$B/pyinstaller.log"; exit 1; }
du -sh "$B/dist/$APP" | sed 's/^/  Bundle: /'

echo "== AppDir"
mkdir -p "$B/AppDir/usr/bin"
cp -a "$B/dist/$APP/." "$B/AppDir/usr/bin/"
cat > "$B/AppDir/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/node-router" "$@"
EOF
chmod +x "$B/AppDir/AppRun"
cat > "$B/AppDir/$APP.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Node-Router
Comment=PipeWire patchbay with virtual microphones and effects
Exec=$APP
Icon=$APP
Terminal=false
Categories=AudioVideo;Audio;Mixer;
X-AppImage-Version=$VERSION
EOF
cp "$DIR/icon.svg" "$B/AppDir/$APP.svg"
ln -sf "$APP.svg" "$B/AppDir/.DirIcon"

echo "== appimagetool"
TOOL="$B/tools/appimagetool-x86_64.AppImage"
if [ ! -x "$TOOL" ]; then
  curl -fsSL -o "$TOOL" "$TOOL_URL"; chmod +x "$TOOL"
  echo "  downloaded: $(sha256sum "$TOOL" | cut -c1-16)…"
fi
rm -f "$OUT"
# APPIMAGE_EXTRACT_AND_RUN: run appimagetool itself without FUSE
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$B/AppDir" "$OUT" >"$B/appimagetool.log" 2>&1 \
  || { tail -30 "$B/appimagetool.log"; exit 1; }
chmod +x "$OUT"
echo; echo "Done: $OUT ($(du -h "$OUT" | cut -f1))"
