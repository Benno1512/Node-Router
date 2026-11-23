#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""Run all tests one after another.

    .venv/bin/python tests/run_all.py            # all
    .venv/bin/python tests/run_all.py fx ghost   # selection (part of the name)

Requirements: running PipeWire + pipewire-pulse, graphical session (the
tests open real windows). Takes about 10 minutes in total.

The router itself must NOT be running: an open router would otherwise remember
all test objects in its config.json and show them as cards afterwards.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NR = HERE.parent
SKIP = 77

TESTS = [  # order: fast/basic first
    ("selftest", NR / "selftest.py", 90),
    ("deps", HERE / "test_deps.py", 90),
    ("menu", HERE / "test_menu.py", 90),
    ("order", HERE / "test_order.py", 150),
    ("volume", HERE / "test_volume.py", 150),
    ("theme", HERE / "test_theme.py", 150),
    ("ignore", HERE / "test_ignore.py", 150),
    ("ghost", HERE / "test_ghost.py", 150),
    ("blocked", HERE / "test_blocked.py", 150),
    ("power", HERE / "test_power.py", 200),
    ("levels", HERE / "test_levels.py", 90),
    ("background", HERE / "test_background.py", 120),
    ("fx", HERE / "test_fx.py", 300),
    ("fx_plugins", HERE / "test_fx_plugins.py", 300),
    ("appimage", HERE / "test_appimage.py", 180),   # skipped without a build
]


def router_running() -> list[int]:
    """PIDs of running router instances (python … main.py in this folder)."""
    pids = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().split(b"\0")
            cwd = os.readlink(p / "cwd")
        except OSError:
            continue
        if any(c.endswith(b"main.py") for c in cmd) and b"python" in cmd[0] and Path(cwd) == NR:
            pids.append(int(p.name))
    return pids


def cleanup() -> list[str]:
    """Remove test leftovers after aborted runs. Only touches test objects:
    modules diy_selftest_*, test streams diy_selftest_*, level meter recorders
    diy_meter_*, effect processes whose
    ID is not in the user's config.json."""
    done = []
    r = subprocess.run(["pactl", "list", "short", "modules"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and "sink_name=diy_selftest_" in parts[2]:
            subprocess.run(["pactl", "unload-module", parts[0]], capture_output=True)
            done.append(f"module {parts[0]}")
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / "cmdline").read_bytes()
        except OSError:
            continue
        argv0 = cmd.split(b"\0")[0]
        if (argv0.endswith((b"pw-play", b"pacat")) and b"diy_selftest_" in cmd) or \
                (argv0.endswith(b"pw-record") and b"diy_meter_" in cmd):
            subprocess.run(["kill", p.name], capture_output=True)
            done.append(f"test stream {p.name}")
    sys.path.insert(0, str(NR))
    import fx as fxlib  # noqa: E402
    try:
        user_ids = {e["id"] for e in json.loads((NR / "config.json").read_text()).get("effects", [])}
    except (OSError, ValueError):
        user_ids = set()
    if fxlib.FX_DIR.exists():
        for conf in fxlib.FX_DIR.glob("*.conf"):
            if conf.stem not in user_ids:
                fxlib.kill(conf.stem); fxlib.delete_files(conf.stem)
                done.append(f"effect {conf.stem}")
    return done


def main() -> int:
    if pids := router_running():
        print(f"Aborted: the router is still running (PID {', '.join(map(str, pids))}). "
              "Close it first – otherwise test objects end up in your config.json.")
        return 2
    if subprocess.run(["pw-dump"], capture_output=True).returncode != 0:
        print("Aborted: PipeWire not reachable (pw-dump fails).")
        return 2
    wanted = sys.argv[1:]
    tests = [t for t in TESTS if not wanted or any(w in t[0] for w in wanted)]
    results = []
    for name, path, timeout in tests:
        print(f"▶ {name:11}", end=" ", flush=True)
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, "-X", "faulthandler", str(path)], cwd=NR,
                               capture_output=True, text=True, timeout=timeout)
            code, out = r.returncode, r.stdout + r.stderr
        except subprocess.TimeoutExpired as e:
            code, out = -1, (e.stdout or b"").decode() + "\nTIMEOUT"
        dt = time.time() - t0
        if name == "selftest":           # selftest.py reports errors in its log, not via exit code
            code = 1 if "ERROR" in out else code
        status = {0: "OK", SKIP: "SKIPPED"}.get(code, "FAILED")
        print(f"{status:13} {dt:5.0f} s")
        if status == "FAILED":
            for line in out.splitlines():
                if line.startswith(("FAIL", "ERROR", "Traceback", "TIMEOUT")) or "Error" in line:
                    print("    " + line)
        elif status == "SKIPPED":
            for line in out.splitlines():
                if line.startswith("SKIP"):
                    print("    " + line)
        results.append(status)
        if leftovers := cleanup():
            print("    cleaned up: " + ", ".join(leftovers))
    ok = results.count("OK")
    print(f"\n{ok}/{len(results)} OK, {results.count('SKIPPED')} skipped, "
          f"{results.count('FAILED')} failed")
    return 0 if "FAILED" not in results else 1


if __name__ == "__main__":
    raise SystemExit(main())
