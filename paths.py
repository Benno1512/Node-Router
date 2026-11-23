# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Storage locations and launch environment – running from source vs. bundled.

From source (python main.py) everything stays next to the program:
    config.json, fx/, plugins/ in the repository folder
As a bundled app (AppImage/PyInstaller) the program folder is read-only or
temporary, therefore:
    ~/.config/node-router/config.json
    ~/.local/share/node-router/{fx,plugins,icon.svg}
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
SRC = Path(__file__).resolve().parent                        # program files
RES = Path(getattr(sys, "_MEIPASS", SRC))                    # bundled data (icon.svg)
APP_ID = "node-router"
LEGACY_ID = "diy-audio-router"          # name up to 0.1.2 ("DIY Audio Router")


def _xdg(var: str, default: str) -> Path:
    return Path(os.environ.get(var) or Path.home() / default)


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / APP_ID if FROZEN else SRC


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / APP_ID if FROZEN else SRC


def _migrate_legacy_dirs() -> None:
    """Bundled: take over folders from before the rename."""
    if not FROZEN:
        return
    for var, default in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share")):
        old, new = _xdg(var, default) / LEGACY_ID, _xdg(var, default) / APP_ID
        if old.is_dir() and not new.exists():
            try:
                old.rename(new)
            except OSError:
                pass


_migrate_legacy_dirs()
CONFIG = Path(os.environ.get("DIY_ROUTER_CONFIG") or config_dir() / "config.json")
FX_DIR = data_dir() / "fx"
PLUGIN_DIR = data_dir() / "plugins"          # plugins placed by the user
BUNDLED_PLUGINS = RES / "plugins"            # bundled ones (see plugins/README.md)


def icon_path() -> Path:
    """Icon for desktop entries: inside the bundle it only exists while the app
    runs (the AppImage is mounted in temp) -> copy it permanently to data_dir()."""
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


def install_bundled_plugins() -> None:
    """Bundled: copy the bundled plugins to data_dir()/plugins.
    Effect processes intentionally keep running when the router quits – but the
    AppImage gets unmounted then. If they loaded the plugin directly from the
    AppImage, they would crash as soon as it is gone."""
    if not FROZEN or not BUNDLED_PLUGINS.is_dir():
        return
    for src in BUNDLED_PLUGINS.rglob("*"):
        if not src.is_file():
            continue
        dst = PLUGIN_DIR / src.relative_to(BUNDLED_PLUGINS)
        try:
            if dst.exists() and dst.stat().st_size == src.stat().st_size and dst.read_bytes() == src.read_bytes():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(dst.suffix + ".tmp")
            shutil.copyfile(src, tmp)
            tmp.replace(dst)                 # atomic: running effects keep the old file
        except OSError:
            pass


def launch_command(minimized: bool = False) -> str:
    """Command line for app menu/autostart, matching how we were started."""
    if os.environ.get("APPIMAGE"):                           # set by the AppImage runtime
        cmd = f'"{os.environ["APPIMAGE"]}"'
    elif FROZEN:
        cmd = f'"{sys.executable}"'
    else:
        cmd = f'"{sys.executable}" "{SRC / "main.py"}"'
    return cmd + (" --minimized" if minimized else "")


def clean_host_env() -> None:
    """Bundled apps set LD_LIBRARY_PATH to their own libraries. Our child
    processes are system programs though (pw-dump, pw-link, pactl, pipewire,
    xdg-open …) – with the bundle libraries they crash or misbehave. So restore
    the original environment for all child processes. (The running process
    itself is not affected: ld.so only reads LD_LIBRARY_PATH at startup.)"""
    if not FROZEN:
        return
    for var in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        orig = os.environ.pop(var + "_ORIG", None)
        if orig is not None:
            os.environ[var] = orig
        else:
            os.environ.pop(var, None)
    # the bundle's Qt/Python paths must not be inherited by other programs
    for var in ("QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "PYTHONHOME", "PYTHONPATH"):
        os.environ.pop(var, None)
