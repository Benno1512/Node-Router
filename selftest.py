# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Selbsttest für den Node-Router. Schreibt alles nach selftest.log."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "selftest.log"
sys.path.insert(0, str(HERE))
out = open(LOG, "w")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s); out.write(s + "\n"); out.flush()


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def step(name, fn):
    log(f"\n=== {name}")
    try:
        fn(); log("OK")
    except Exception:
        log("FEHLER:\n" + traceback.format_exc())


def env():
    log("python", sys.version)
    for t in ("pw-dump", "pw-link", "pactl", "wpctl"):
        log(t, shutil.which(t))
    log(sh(["pactl", "info"])[1])
    log(sh(["pipewire", "--version"])[1])
    log(sh(["wireplumber", "--version"])[1])


import pw_backend as pw  # noqa: E402

TEST = "diy_selftest_mic"


def graph():
    g = pw.read_graph()
    log(f"{len(g.nodes)} Audio-Nodes, {len(g.links)} Links")
    for n in sorted(g.nodes.values(), key=lambda n: n.media_class):
        side = "LINKS " if n.is_left else "RECHTS" if n.is_right else "  -   "
        log(f"  [{side}] id={n.id:<4} {n.media_class:<22} {n.label!r:<40} "
            f"in={[p.channel for p in n.in_ports]} "
            f"out={[p.channel + ('(mon)' if p.monitor else '') for p in n.out_ports]}")


def virtual_mic():
    pw.remove_virtual_mic(TEST)
    pw.create_virtual_mic("Selftest Mic", TEST)
    time.sleep(1)
    g = pw.read_graph()
    nodes = [n for n in g.nodes.values() if n.name == TEST]
    assert nodes, "virtuelles Mikro nicht im Graph gefunden"
    n = nodes[0]
    log(f"  class={n.media_class} label={n.label!r} virt={n.is_virtual_mic} "
        f"right={n.is_right} in={[p.name for p in n.in_ports]} out={[p.name for p in n.out_ports]}")
    assert n.is_right, "virtuelles Mikro landet nicht auf der rechten Seite"
    assert n.label == "Selftest Mic", f"Beschreibung abgeschnitten: {n.label!r}"
    sinks = [x for x in g.nodes.values() if x.media_class == "Audio/Sink"]
    assert all(p.monitor for x in sinks for p in x.out_ports), "Monitor-Ports nicht erkannt"
    log("  pactl sources:")
    log("   " + "\n   ".join(l for l in sh(["pactl", "list", "short", "sources"])[1].splitlines()
                            if TEST in l) or "   (nicht als Source sichtbar!)")

    srcs = [s for s in g.nodes.values() if s.is_left]
    assert srcs, "keine Quelle zum Testen"
    s = srcs[0]
    log(f"  verbinde {s.label!r} -> Selftest Mic: {pw.port_pairs(s, n)}")
    errs = pw.connect(g, s.id, n.id)
    assert not errs, errs
    time.sleep(0.5)
    g = pw.read_graph()
    links = [l for l in g.links if l.out_node == s.id and l.in_node == n.id]
    log(f"  {len(links)} Links erstellt")
    assert links, "Link wurde nicht erstellt"
    pw.disconnect(g, s.id, n.id)
    time.sleep(0.5)
    g = pw.read_graph()
    assert not [l for l in g.links if l.out_node == s.id and l.in_node == n.id], "Trennen fehlgeschlagen"
    log("  getrennt")


def cleanup():
    pw.remove_virtual_mic(TEST)
    time.sleep(0.5)
    assert TEST not in sh(["pactl", "list", "short", "modules"])[1], "Modul noch geladen"


def gui():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    import main as m
    m.CONFIG = HERE / "selftest_config.json"
    app = QApplication.instance() or QApplication([])
    w = m.MainWindow(); w.show()
    QTimer.singleShot(3000, app.quit)
    app.exec()
    log(f"  Nodes in Szene: {len(w.view.node_items)}, Wires: {len(w.view.wires)}")
    shot = HERE / "selftest_screenshot.png"
    w.grab().save(str(shot)); log(f"  Screenshot: {shot}")
    assert w.view.node_items, "keine Nodes angezeigt"
    (HERE / "selftest_config.json").unlink(missing_ok=True)


step("Umgebung", env)
step("Graph lesen", graph)
step("Virtuelles Mikro + Verbinden/Trennen", virtual_mic)
step("Aufräumen", cleanup)
step("GUI (offscreen)", gui)
log(f"\nFertig. Log: {LOG}")
