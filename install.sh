#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
# Node-Router – install for the current user (no root needed).
#
#   ./install.sh                  venv + PySide6, app menu entry
#   ./install.sh --autostart      additionally start (minimized) at login
#   ./install.sh --uninstall      remove app menu and autostart entries
#                                 (program, venv and config.json stay)
#
# Environment: VENV=<path> (default: ./.venv), XDG_DATA_HOME / XDG_CONFIG_HOME.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="node-router"
VENV="${VENV:-$DIR/.venv}"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

AUTOSTART=0; UNINSTALL=0
for a in "$@"; do
  case "$a" in
    --autostart) AUTOSTART=1 ;;
    --with-rnnoise) ;;   # obsolete: plugins are bundled now
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a (see --help)"; exit 2 ;;
  esac
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; }

if [ "$UNINSTALL" = 1 ]; then
  rm -f "$APPS_DIR/$APP_ID.desktop" "$AUTOSTART_DIR/$APP_ID.desktop" \
        "$APPS_DIR/diy-audio-router.desktop" "$AUTOSTART_DIR/diy-audio-router.desktop"
  ok "App menu and autostart entries removed"
  exit 0
fi

echo "== System requirements"
missing=0
for cmd in pw-dump pw-link pw-cli wpctl pactl pipewire; do
  if command -v "$cmd" >/dev/null; then ok "$cmd"; else fail "$cmd is missing"; missing=1; fi
done
if pactl info 2>/dev/null | grep -q "PipeWire"; then ok "pipewire-pulse is running"
else fail "pipewire-pulse is not running (package pipewire-pulse)"; missing=1; fi
if [ "$missing" = 1 ]; then
  echo; echo "Install the missing system packages:  ./install-deps.sh"
  exit 1
fi
PY="$(command -v python3 || true)"
[ -n "$PY" ] || { fail "python3 is missing"; exit 1; }
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { fail "Python ≥ 3.10 required"; exit 1; }
ok "$("$PY" --version)"

echo "== Python environment ($VENV)"
if [ ! -x "$VENV/bin/python" ]; then
  "$PY" -m venv "$VENV" || { fail "could not create the venv (package python3-venv?)"; exit 1; }
  ok "venv created"
fi
if "$VENV/bin/python" -c 'import PySide6' 2>/dev/null; then
  ok "PySide6 present ($("$VENV/bin/python" -c 'import PySide6; print(PySide6.__version__)'))"
else
  "$VENV/bin/python" -m pip install --upgrade pip >/dev/null
  "$VENV/bin/python" -m pip install -r "$DIR/requirements.txt"
  ok "PySide6 installed"
fi

echo "== Effect plugins (bundled in plugins/)"
for f in librnnoise_ladspa.so lsp-plugins-ladspa.so; do
  if [ -f "$DIR/plugins/$f" ]; then ok "$f"; else warn "$f missing in plugins/ – is the repository complete?"; fi
done

echo "== App menu"
entry() {   # $1 = 1: start minimized
  local extra=""; [ "$1" = 1 ] && extra=" --minimized"
  cat <<EOF
[Desktop Entry]
Type=Application
Name=Node-Router
Comment=PipeWire patchbay with virtual microphones and effects
Exec="$VENV/bin/python" "$DIR/main.py"$extra
Icon=$DIR/icon.svg
Terminal=false
Categories=AudioVideo;Audio;Mixer;
EOF
}
mkdir -p "$APPS_DIR"
# remove entries from before the rename ("DIY Audio Router")
if [ -f "$AUTOSTART_DIR/diy-audio-router.desktop" ]; then AUTOSTART=1; fi
rm -f "$APPS_DIR/diy-audio-router.desktop" "$AUTOSTART_DIR/diy-audio-router.desktop"
entry 0 > "$APPS_DIR/$APP_ID.desktop"
ok "Entry: $APPS_DIR/$APP_ID.desktop"
if [ "$AUTOSTART" = 1 ]; then
  mkdir -p "$AUTOSTART_DIR"
  { entry 1; echo "X-GNOME-Autostart-enabled=true"; } > "$AUTOSTART_DIR/$APP_ID.desktop"
  ok "Autostart: $AUTOSTART_DIR/$APP_ID.desktop"
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo; echo "Done. Start: app menu → \"Node-Router\" or"
echo "  \"$VENV/bin/python\" \"$DIR/main.py\""
