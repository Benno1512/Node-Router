#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – DIY Audio Router
# DIY Audio Router – Installation für den aktuellen Benutzer (kein root nötig).
#
#   ./install.sh                  venv + PySide6, Startmenü-Eintrag
#   ./install.sh --autostart      zusätzlich beim Anmelden (minimiert) starten
#   ./install.sh --with-rnnoise   RNNoise-Plugin (Rauschunterdrückung) herunterladen
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
RNNOISE_URL="https://github.com/werman/noise-suppression-for-voice/releases/download/v1.10/linux-rnnoise.zip"
RNNOISE_SHA256="811390b6eb6e28dde023c70590c74d26e74ebb2e595bcf4b95af2341db160e99"

AUTOSTART=0; RNNOISE=0; UNINSTALL=0
for a in "$@"; do
  case "$a" in
    --autostart) AUTOSTART=1 ;;
    --with-rnnoise) RNNOISE=1 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
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
  echo; echo "Ubuntu/Debian: sudo apt install pipewire pipewire-pulse pipewire-bin wireplumber pulseaudio-utils"
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

echo "== Optionale Effekt-Plugins"
if [ -f /usr/lib/ladspa/lsp-plugins-ladspa.so ] || [ -f /usr/lib/x86_64-linux-gnu/ladspa/lsp-plugins-ladspa.so ]; then
  ok "LSP-Plugins (Kompressor, Ducking)"
else
  warn "LSP-Plugins fehlen – Kompressor/Ducking ausgegraut. Nachinstallieren: sudo apt install lsp-plugins-ladspa"
fi
if [ "$RNNOISE" = 1 ] && [ ! -f "$DIR/plugins/librnnoise_ladspa.so" ]; then
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  echo "  lade $RNNOISE_URL"
  curl -fsSL -o "$tmp/rnnoise.zip" "$RNNOISE_URL"
  echo "$RNNOISE_SHA256  $tmp/rnnoise.zip" | sha256sum -c --quiet - || { fail "Prüfsumme falsch – abgebrochen"; exit 1; }
  mkdir -p "$DIR/plugins"
  "$PY" -I -c 'import sys, zipfile; open(sys.argv[2], "wb").write(zipfile.ZipFile(sys.argv[1]).read("linux-rnnoise/ladspa/librnnoise_ladspa.so"))' \
        "$tmp/rnnoise.zip" "$DIR/plugins/librnnoise_ladspa.so"
  ok "RNNoise-Plugin nach plugins/ entpackt (v1.10, Prüfsumme ok)"
fi
if [ -f "$DIR/plugins/librnnoise_ladspa.so" ]; then
  if ldd "$DIR/plugins/librnnoise_ladspa.so" | grep -q "not found"; then
    warn "RNNoise: Bibliothek fehlt ($(ldd "$DIR/plugins/librnnoise_ladspa.so" | awk '/not found/{print $1}' | paste -sd' ')) – meist: sudo apt install libatomic1"
  else ok "RNNoise (Rauschunterdrückung)"; fi
else
  warn "RNNoise fehlt – Rauschunterdrückung ausgegraut. Mit ./install.sh --with-rnnoise herunterladen"
fi

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
