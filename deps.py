# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""Check system requirements and name the matching install command.

Bundled are Python/Qt (AppImage) and the effect plugins (plugins/). PipeWire,
pipewire-pulse, WirePlumber and their command line tools must come from the
system – this file checks them (same package lists as install-deps.sh). Only
Ubuntu 24.04 is tested; the other package names follow the official
repositories of the respective distribution.
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
    """List of readable problems; empty = everything present."""
    out = [f"Program \"{t}\" is missing" for t in TOOLS if shutil.which(t) is None]
    if shutil.which("pactl"):
        try:
            info = subprocess.run(["pactl", "info"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.TimeoutExpired):
            info = ""
        if "PipeWire" not in info:
            out.append("The sound server is not PipeWire (pipewire-pulse is not running – "
                       "maybe PulseAudio is still active)")
    if shutil.which("pw-dump"):
        try:
            ok = subprocess.run(["pw-dump"], capture_output=True, timeout=5).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        if not ok:
            out.append("PipeWire is not reachable (service not running)")
    return out


def help_text(probs: list[str]) -> str:
    cmd = install_command()
    lines = ["Node-Router needs something that is missing:", ""]
    lines += [f"  • {p}" for p in probs]
    lines += ["", "Install in a terminal:" if cmd else
              "Please install PipeWire, pipewire-pulse, WirePlumber and pactl with your package manager.", ""]
    if cmd:
        lines += [f"  {cmd}", "", "and enable the sound server:", f"  {SERVICES}"]
    lines += ["", "Then log out and back in (or reboot).",
              "Alternatively the script install-deps.sh from the repository does all of this in one step."]
    return "\n".join(lines)
