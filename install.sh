#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – DIY Audio Router
# DIY Audio Router – Installation für den aktuellen Benutzer (kein root nötig).
#
#   ./install.sh                  venv + PySide6, Startmenü-Eintrag
#   ./install.sh --autostart      zusätzlich beim Anmelden (minimiert) starten
#   ./install.sh --uninstall      Startmenü- und Autostart-Eintrag entfernen
#                                 (Programm, venv und config.json bleiben)
#
# Umgebungsvariablen: VENV=<Pfad> (Standard: ./.venv), XDG_DATA_HOME / XDG_CONFIG_HOME.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="diy-audio-router"
VENV="${VENV:-$DIR/.venv}"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

AUTOSTART=0; UNINSTALL=0
for a in "$@"; do
  case "$a" in
    --autostart) AUTOSTART=1 ;;
    --with-rnnoise) ;;   # veraltet: Plugins sind jetzt mitgeliefert
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "Unbekannte Option: $a (siehe --help)"; exit 2 ;;
  esac
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; }

if [ "$UNINSTALL" = 1 ]; then
  rm -f "$APPS_DIR/$APP_ID.desktop" "$AUTOSTART_DIR/$APP_ID.desktop"
  ok "Startmenü- und Autostart-Eintrag entfernt"
  exit 0
fi

echo "== Systemvoraussetzungen"
missing=0
for cmd in pw-dump pw-link pw-cli wpctl pactl pipewire; do
  if command -v "$cmd" >/dev/null; then ok "$cmd"; else fail "$cmd fehlt"; missing=1; fi
done
if pactl info 2>/dev/null | grep -q "PipeWire"; then ok "pipewire-pulse läuft"
else fail "pipewire-pulse läuft nicht (Paket pipewire-pulse)"; missing=1; fi
if [ "$missing" = 1 ]; then
  echo; echo "Fehlende Systempakete installieren:  ./install-deps.sh"
  exit 1
fi
PY="$(command -v python3 || true)"
[ -n "$PY" ] || { fail "python3 fehlt"; exit 1; }
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { fail "Python ≥ 3.10 nötig"; exit 1; }
ok "$("$PY" --version)"

echo "== Python-Umgebung ($VENV)"
if [ ! -x "$VENV/bin/python" ]; then
  "$PY" -m venv "$VENV" || { fail "venv konnte nicht angelegt werden (Paket python3-venv?)"; exit 1; }
  ok "venv angelegt"
fi
if "$VENV/bin/python" -c 'import PySide6' 2>/dev/null; then
  ok "PySide6 vorhanden ($("$VENV/bin/python" -c 'import PySide6; print(PySide6.__version__)'))"
else
  "$VENV/bin/python" -m pip install --upgrade pip >/dev/null
  "$VENV/bin/python" -m pip install -r "$DIR/requirements.txt"
  ok "PySide6 installiert"
fi

echo "== Effekt-Plugins (mitgeliefert in plugins/)"
for f in librnnoise_ladspa.so lsp-plugins-ladspa.so; do
  if [ -f "$DIR/plugins/$f" ]; then ok "$f"; else warn "$f fehlt im Ordner plugins/ – Repository vollständig?"; fi
done

echo "== Startmenü"
entry() {   # $1 = 1: minimiert starten
  local extra=""; [ "$1" = 1 ] && extra=" --minimized"
  cat <<EOF
[Desktop Entry]
Type=Application
Name=DIY Audio Router
Comment=PipeWire-Patchbay mit virtuellen Mikrofonen und Effekten
Exec="$VENV/bin/python" "$DIR/main.py"$extra
Icon=$DIR/icon.svg
Terminal=false
Categories=AudioVideo;Audio;Mixer;
EOF
}
mkdir -p "$APPS_DIR"
entry 0 > "$APPS_DIR/$APP_ID.desktop"
ok "Eintrag: $APPS_DIR/$APP_ID.desktop"
if [ "$AUTOSTART" = 1 ]; then
  mkdir -p "$AUTOSTART_DIR"
  { entry 1; echo "X-GNOME-Autostart-enabled=true"; } > "$AUTOSTART_DIR/$APP_ID.desktop"
  ok "Autostart: $AUTOSTART_DIR/$APP_ID.desktop"
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo; echo "Fertig. Start: Startmenü → „DIY Audio Router“ oder"
echo "  \"$VENV/bin/python\" \"$DIR/main.py\""
