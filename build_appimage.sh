#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – DIY Audio Router
#
# Baut DIY-Audio-Router-<version>-x86_64.AppImage – eine einzelne startbare Datei
# mit Python, PySide6 und Qt. PipeWire-Werkzeuge (pw-dump, pw-link, pactl,
# pipewire) kommen weiterhin vom System.
#
#   ./build_appimage.sh            Ergebnis: build/DIY-Audio-Router-<version>-x86_64.AppImage
#
# Lädt beim ersten Lauf: PySide6 + PyInstaller (PyPI) in build/venv und
# appimagetool (github.com/AppImage/appimagetool) nach build/tools.
# Hinweis: Das AppImage läuft auf Systemen mit mindestens der glibc-Version des
# Build-Rechners (hier gebaut: Ubuntu 24.04 → glibc 2.39).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
B="$DIR/build"
APP=diy-audio-router
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$DIR/main.py")"
OUT="$B/DIY-Audio-Router-$VERSION-x86_64.AppImage"
TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
mkdir -p "$B/tools"

echo "== Build-Umgebung ($B/venv)"
if [ ! -x "$B/venv/bin/python" ]; then python3 -m venv "$B/venv"; fi
"$B/venv/bin/python" -m pip install --quiet --upgrade pip
"$B/venv/bin/python" -m pip install --quiet -r "$DIR/requirements.txt" "pyinstaller>=6,<7"
"$B/venv/bin/python" -c 'import PySide6, PyInstaller; print("  PySide6", PySide6.__version__, "· PyInstaller", PyInstaller.__version__)'

echo "== Bündeln (PyInstaller)"
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
exec "$HERE/usr/bin/diy-audio-router" "$@"
EOF
chmod +x "$B/AppDir/AppRun"
cat > "$B/AppDir/$APP.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=DIY Audio Router
Comment=PipeWire-Patchbay mit virtuellen Mikrofonen und Effekten
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
  echo "  geladen: $(sha256sum "$TOOL" | cut -c1-16)…"
fi
rm -f "$OUT"
# APPIMAGE_EXTRACT_AND_RUN: appimagetool selbst ohne FUSE ausführen
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$B/AppDir" "$OUT" >"$B/appimagetool.log" 2>&1 \
  || { tail -30 "$B/appimagetool.log"; exit 1; }
chmod +x "$OUT"
echo; echo "Fertig: $OUT ($(du -h "$OUT" | cut -f1))"
