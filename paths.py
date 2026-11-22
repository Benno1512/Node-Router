# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – DIY Audio Router
"""Speicherorte und Start-Umgebung – Quellcode-Betrieb vs. gebündelte App.

Aus dem Quellcode (python main.py) bleibt alles neben dem Programm:
    config.json, fx/, plugins/ in node_router/
Als gebündelte App (AppImage/PyInstaller) ist der Programmordner schreibgeschützt
bzw. temporär, daher:
    ~/.config/diy-audio-router/config.json
    ~/.local/share/diy-audio-router/{fx,plugins,icon.svg}
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
SRC = Path(__file__).resolve().parent                        # Programmdateien
RES = Path(getattr(sys, "_MEIPASS", SRC))                    # mitgelieferte Daten (icon.svg)
APP_ID = "diy-audio-router"


def _xdg(var: str, default: str) -> Path:
    return Path(os.environ.get(var) or Path.home() / default)


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / APP_ID if FROZEN else SRC


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / APP_ID if FROZEN else SRC


CONFIG = Path(os.environ.get("DIY_ROUTER_CONFIG") or config_dir() / "config.json")
FX_DIR = data_dir() / "fx"
PLUGIN_DIR = data_dir() / "plugins"


def icon_path() -> Path:
    """Icon für Desktop-Einträge: im Bundle liegt es nur, solange die App läuft
    (AppImage wird ins Temp eingehängt) -> dauerhaft nach data_dir() kopieren."""
    src = RES / "icon.svg"
    if not FROZEN:
        return src
    dst = data_dir() / "icon.svg"
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            shutil.copyfile(src, dst)
        return dst
    except OSError:
        return src


def launch_command(minimized: bool = False) -> str:
    """Kommandozeile für Startmenü/Autostart, passend zur Art des Starts."""
    if os.environ.get("APPIMAGE"):                           # vom AppImage-Runtime gesetzt
        cmd = f'"{os.environ["APPIMAGE"]}"'
    elif FROZEN:
        cmd = f'"{sys.executable}"'
    else:
        cmd = f'"{sys.executable}" "{SRC / "main.py"}"'
    return cmd + (" --minimized" if minimized else "")


def clean_host_env() -> None:
    """Gebündelte Apps setzen LD_LIBRARY_PATH auf ihre eigenen Bibliotheken.
    Unsere Kindprozesse sind aber System-Programme (pw-dump, pw-link, pactl,
    pipewire, xdg-open …) – mit den Bundle-Bibliotheken stürzen sie ab oder
    verhalten sich falsch. Daher für alle Kindprozesse die Original-Umgebung
    wiederherstellen. (Der laufende Prozess selbst ist davon nicht betroffen:
    ld.so liest LD_LIBRARY_PATH nur beim Start.)"""
    if not FROZEN:
        return
    for var in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        orig = os.environ.pop(var + "_ORIG", None)
        if orig is not None:
            os.environ[var] = orig
        else:
            os.environ.pop(var, None)
    # Qt/Python-Pfade des Bundles sollen nicht an andere Programme vererbt werden
    for var in ("QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "PYTHONHOME", "PYTHONPATH"):
        os.environ.pop(var, None)
