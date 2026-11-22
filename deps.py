# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – DIY Audio Router
"""Systemvoraussetzungen prüfen und den passenden Installationsbefehl nennen.

Mitgeliefert werden Python/Qt (AppImage) und die Effekt-Plugins (plugins/).
Vom System kommen müssen PipeWire, pipewire-pulse, WirePlumber und deren
Kommandozeilen-Werkzeuge – das prüft diese Datei (gleiche Paketlisten wie
install-deps.sh). Getestet ist nur Ubuntu 24.04; die anderen Paketnamen
entsprechen den Paketquellen der jeweiligen Distribution.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

TOOLS = ["pipewire", "pw-dump", "pw-link", "pw-cli", "wpctl", "pactl"]

PACKAGES = {
    "debian": ["pipewire", "pipewire-pulse", "pipewire-bin", "wireplumber", "pulseaudio-utils",
               "libsndfile1", "libxcb-cursor0"],
    "fedora": ["pipewire", "pipewire-pulseaudio", "pipewire-utils", "wireplumber", "pulseaudio-utils",
               "libsndfile", "xcb-util-cursor"],
    "arch": ["pipewire", "pipewire-pulse", "wireplumber", "libpulse", "libsndfile", "xcb-util-cursor"],
    "suse": ["pipewire", "pipewire-pulseaudio", "pipewire-tools", "wireplumber", "pulseaudio-utils",
             "libsndfile1", "libxcb-cursor0"],
}
INSTALLER = {"debian": "sudo apt install", "fedora": "sudo dnf install",
             "arch": "sudo pacman -S --needed", "suse": "sudo zypper install"}
SERVICES = "systemctl --user enable --now pipewire pipewire-pulse wireplumber"


def os_release() -> dict[str, str]:
    d = {}
    try:
        for line in Path(os.environ.get("OS_RELEASE_FILE") or "/etc/os-release").read_text().splitlines():
            k, _, v = line.partition("=")
            d[k] = v.strip().strip('"')
    except OSError:
        pass
    return d


def family() -> str | None:
    r = os_release()
    ids = [r.get("ID", "")] + r.get("ID_LIKE", "").split()
    for i in ids:
        if i in ("debian", "ubuntu", "linuxmint", "pop", "elementary", "zorin", "neon"):
            return "debian"
        if i in ("fedora", "rhel", "centos", "nobara"):
            return "fedora"
        if i in ("arch", "manjaro", "endeavouros", "cachyos", "garuda"):
            return "arch"
        if i.startswith("opensuse") or i in ("suse", "sles"):
            return "suse"
    return None


def install_command() -> str | None:
    f = family()
    return f"{INSTALLER[f]} {' '.join(PACKAGES[f])}" if f else None


def problems() -> list[str]:
    """Liste lesbarer Probleme; leer = alles da."""
    out = [f"Programm „{t}“ fehlt" for t in TOOLS if shutil.which(t) is None]
    if shutil.which("pactl"):
        try:
            info = subprocess.run(["pactl", "info"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.TimeoutExpired):
            info = ""
        if "PipeWire" not in info:
            out.append("Der Sound-Server ist nicht PipeWire (pipewire-pulse läuft nicht – "
                       "evtl. noch PulseAudio aktiv)")
    if shutil.which("pw-dump"):
        try:
            ok = subprocess.run(["pw-dump"], capture_output=True, timeout=5).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        if not ok:
            out.append("PipeWire ist nicht erreichbar (Dienst läuft nicht)")
    return out


def help_text(probs: list[str]) -> str:
    cmd = install_command()
    lines = ["Es fehlt etwas, damit der DIY Audio Router arbeiten kann:", ""]
    lines += [f"  • {p}" for p in probs]
    lines += ["", "Im Terminal installieren:" if cmd else
              "Bitte PipeWire, pipewire-pulse, WirePlumber und pactl über die Paketverwaltung installieren.", ""]
    if cmd:
        lines += [f"  {cmd}", "", "und den Sound-Server einschalten:", f"  {SERVICES}"]
    lines += ["", "Danach abmelden und wieder anmelden (oder neu starten).",
              "Alternativ erledigt das Skript install-deps.sh aus dem Repository alles in einem Schritt."]
    return "\n".join(lines)
