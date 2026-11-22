#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – DIY Audio Router
"""Alle Tests nacheinander ausführen.

    cd node_router && ../.venv/bin/python tests/run_all.py            # alle
    cd node_router && ../.venv/bin/python tests/run_all.py fx ghost   # Auswahl (Teilname)

Voraussetzungen: laufendes PipeWire + pipewire-pulse, grafische Sitzung (die
Tests öffnen echte Fenster). Dauer insgesamt ca. 10 Minuten.

Der Router selbst darf dabei NICHT laufen: Ein offener Router merkt sich sonst
alle Test-Objekte in seiner config.json und zeigt sie danach als Karten an.
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

TESTS = [  # Reihenfolge: schnell/grundlegend zuerst
    ("selftest", NR / "selftest.py", 90),
    ("menu", HERE / "test_menu.py", 90),
    ("order", HERE / "test_order.py", 150),
    ("volume", HERE / "test_volume.py", 150),
    ("theme", HERE / "test_theme.py", 150),
    ("ignore", HERE / "test_ignore.py", 150),
    ("ghost", HERE / "test_ghost.py", 150),
    ("blocked", HERE / "test_blocked.py", 150),
    ("power", HERE / "test_power.py", 200),
    ("background", HERE / "test_background.py", 120),
    ("fx", HERE / "test_fx.py", 300),
    ("fx_plugins", HERE / "test_fx_plugins.py", 300),
]


def router_running() -> list[int]:
    """PIDs laufender Router-Instanzen (python … main.py in diesem Ordner)."""
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
    """Test-Reste nach Abbrüchen entfernen. Fasst nur Test-Objekte an:
    Module diy_selftest_*, Test-Streams diy_selftest_*, Effekt-Prozesse, deren
    ID nicht in der config.json des Nutzers steht."""
    done = []
    r = subprocess.run(["pactl", "list", "short", "modules"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and "sink_name=diy_selftest_" in parts[2]:
            subprocess.run(["pactl", "unload-module", parts[0]], capture_output=True)
            done.append(f"Modul {parts[0]}")
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / "cmdline").read_bytes()
        except OSError:
            continue
        if cmd.split(b"\0")[0].endswith((b"pw-play", b"pacat")) and b"diy_selftest_" in cmd:
            subprocess.run(["kill", p.name], capture_output=True)
            done.append(f"Test-Stream {p.name}")
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
                done.append(f"Effekt {conf.stem}")
    return done


def main() -> int:
    if pids := router_running():
        print(f"Abbruch: Der Router läuft noch (PID {', '.join(map(str, pids))}). "
              "Bitte zuerst schließen – sonst landen Test-Objekte in deiner config.json.")
        return 2
    if subprocess.run(["pw-dump"], capture_output=True).returncode != 0:
        print("Abbruch: PipeWire nicht erreichbar (pw-dump schlägt fehl).")
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
            code, out = -1, (e.stdout or b"").decode() + "\nZEITÜBERSCHREITUNG"
        dt = time.time() - t0
        if name == "selftest":           # selftest.py meldet Fehler im Log statt per Exit-Code
            code = 1 if "FEHLER" in out else code
        status = {0: "OK", SKIP: "ÜBERSPRUNGEN"}.get(code, "FEHLER")
        print(f"{status:13} {dt:5.0f} s")
        if status == "FEHLER":
            for line in out.splitlines():
                if line.startswith(("FAIL", "FEHLER", "Traceback", "ZEIT")) or "Error" in line:
                    print("    " + line)
        elif status == "ÜBERSPRUNGEN":
            for line in out.splitlines():
                if line.startswith("SKIP"):
                    print("    " + line)
        results.append(status)
        if leftovers := cleanup():
            print("    aufgeräumt: " + ", ".join(leftovers))
    ok = results.count("OK")
    print(f"\n{ok}/{len(results)} OK, {results.count('ÜBERSPRUNGEN')} übersprungen, "
          f"{results.count('FEHLER')} Fehler")
    return 0 if "FEHLER" not in results else 1


if __name__ == "__main__":
    raise SystemExit(main())
