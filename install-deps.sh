#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
#
# Installs everything Node-Router needs from the system (PipeWire,
# pipewire-pulse, WirePlumber, pactl, Qt helper library) and enables the
# sound server. Detects Ubuntu/Debian/Mint, Fedora, Arch/Manjaro, openSUSE.
# Python, Qt and the effect plugins are already in the AppImage / repository.
#
#   ./install-deps.sh           shows the command and asks before running it
#   ./install-deps.sh --yes     without asking
#   ./install-deps.sh --print   only show, run nothing
#
# Only Ubuntu 24.04 is tested; the package names for the other distributions
# follow their official repositories.
set -euo pipefail

YES=0; PRINT=0
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;;
    --print) PRINT=1 ;;
    -h|--help) sed -n '5,17p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a (see --help)"; exit 2 ;;
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
    echo "Distribution not recognized (${PRETTY_NAME:-unknown})."
    echo "Please install: PipeWire, pipewire-pulse, WirePlumber, pactl (pulseaudio-utils/libpulse),"
    echo "libsndfile and xcb-util-cursor (libxcb-cursor0)."
    exit 1 ;;
esac
SERVICES="systemctl --user enable --now pipewire pipewire-pulse wireplumber"

echo "System: ${PRETTY_NAME:-unknown}"
echo
echo "1) Install packages:"
echo "   $CMD"
echo "2) Enable the sound server:"
echo "   $SERVICES"
if systemctl --user is-active --quiet pulseaudio.service 2>/dev/null; then
  echo "   (PulseAudio is still running – it will be disabled: systemctl --user disable --now pulseaudio.service pulseaudio.socket)"
fi
echo
[ "$PRINT" = 1 ] && exit 0
if [ "$YES" != 1 ]; then
  read -r -p "Run now? [y/N] " ans
  case "$ans" in y|Y|yes|Yes|j|J) ;; *) echo "Cancelled."; exit 0 ;; esac
fi

$CMD
if systemctl --user is-active --quiet pulseaudio.service 2>/dev/null; then
  systemctl --user disable --now pulseaudio.service pulseaudio.socket || true
fi
$SERVICES || true

echo
echo "== Check"
ok=1
for t in pipewire pw-dump pw-link pw-cli wpctl pactl; do
  if command -v "$t" >/dev/null; then echo "  ✓ $t"; else echo "  ✗ $t is missing"; ok=0; fi
done
if pactl info 2>/dev/null | grep -q PipeWire; then echo "  ✓ sound server is PipeWire"
else echo "  ! sound server is not PipeWire yet – please log out and back in"; ok=0; fi
[ "$ok" = 1 ] && echo "All set. Start Node-Router now." || true
