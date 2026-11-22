#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – DIY Audio Router
#
# Installiert alles, was der DIY Audio Router vom System braucht (PipeWire,
# pipewire-pulse, WirePlumber, pactl, Qt-Hilfsbibliothek) und schaltet den
# Sound-Server ein. Erkennt Ubuntu/Debian/Mint, Fedora, Arch/Manjaro, openSUSE.
# Python, Qt und die Effekt-Plugins sind bereits im AppImage bzw. Repository.
#
#   ./install-deps.sh           zeigt den Befehl und fragt vor dem Ausführen
#   ./install-deps.sh --yes     ohne Rückfrage
#   ./install-deps.sh --print   nur anzeigen, nichts ausführen
#
# Getestet ist nur Ubuntu 24.04; die Paketnamen der anderen Distributionen
# entsprechen deren offiziellen Paketquellen.
set -euo pipefail

YES=0; PRINT=0
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;;
    --print) PRINT=1 ;;
    -h|--help) sed -n '5,17p' "$0"; exit 0 ;;
    *) echo "Unbekannte Option: $a (siehe --help)"; exit 2 ;;
  esac
done

. "${OS_RELEASE_FILE:-/etc/os-release}" 2>/dev/null || true
ids=" ${ID:-} ${ID_LIKE:-} "
case "$ids" in
  *" ubuntu "*|*" debian "*|*" linuxmint "*|*" pop "*|*" neon "*|*" elementary "*|*" zorin "*)
    CMD="sudo apt install -y pipewire pipewire-pulse pipewire-bin wireplumber pulseaudio-utils libsndfile1 libxcb-cursor0" ;;
  *" fedora "*|*" rhel "*|*" nobara "*)
    CMD="sudo dnf install -y pipewire pipewire-pulseaudio pipewire-utils wireplumber pulseaudio-utils libsndfile xcb-util-cursor" ;;
  *" arch "*|*" manjaro "*|*" endeavouros "*|*" cachyos "*|*" garuda "*)
    CMD="sudo pacman -S --needed --noconfirm pipewire pipewire-pulse wireplumber libpulse libsndfile xcb-util-cursor" ;;
  *opensuse*|*" suse "*|*" sles "*)
    CMD="sudo zypper install -y pipewire pipewire-pulseaudio pipewire-tools wireplumber pulseaudio-utils libsndfile1 libxcb-cursor0" ;;
  *)
    echo "Distribution nicht erkannt (${PRETTY_NAME:-unbekannt})."
    echo "Bitte installieren: PipeWire, pipewire-pulse, WirePlumber, pactl (pulseaudio-utils/libpulse),"
    echo "libsndfile und xcb-util-cursor (libxcb-cursor0)."
    exit 1 ;;
esac
SERVICES="systemctl --user enable --now pipewire pipewire-pulse wireplumber"

echo "System: ${PRETTY_NAME:-unbekannt}"
echo
echo "1) Pakete installieren:"
echo "   $CMD"
echo "2) Sound-Server einschalten:"
echo "   $SERVICES"
if systemctl --user is-active --quiet pulseaudio.service 2>/dev/null; then
  echo "   (PulseAudio läuft noch – wird abgeschaltet: systemctl --user disable --now pulseaudio.service pulseaudio.socket)"
fi
echo
[ "$PRINT" = 1 ] && exit 0
if [ "$YES" != 1 ]; then
  read -r -p "Jetzt ausführen? [j/N] " ans
  case "$ans" in j|J|y|Y|ja|Ja) ;; *) echo "Abgebrochen."; exit 0 ;; esac
fi

$CMD
if systemctl --user is-active --quiet pulseaudio.service 2>/dev/null; then
  systemctl --user disable --now pulseaudio.service pulseaudio.socket || true
fi
$SERVICES || true

echo
echo "== Prüfung"
ok=1
for t in pipewire pw-dump pw-link pw-cli wpctl pactl; do
  if command -v "$t" >/dev/null; then echo "  ✓ $t"; else echo "  ✗ $t fehlt"; ok=0; fi
done
if pactl info 2>/dev/null | grep -q PipeWire; then echo "  ✓ Sound-Server ist PipeWire"
else echo "  ! Sound-Server ist noch nicht PipeWire – bitte ab- und wieder anmelden"; ok=0; fi
[ "$ok" = 1 ] && echo "Alles bereit. Jetzt den DIY Audio Router starten." || true
