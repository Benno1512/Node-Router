# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""Ghost cards: test app (pacat) disappears/returns; test mic as target. Temp config."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (also sets sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtWidgets import QApplication
import main as m, pw_backend as pw

m.CONFIG = OUT / "ghost_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0
APP, MIC = "diy_selftest_app", "diy_selftest_ghost"
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
def start():
    return subprocess.Popen(["pacat", "--playback", "--raw", "--format=s16le", "--rate=48000", "--channels=2",
                             f"--client-name={APP}", "/dev/zero"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def stop(p): p.terminate(); p.wait()
def items(v, key): return [i for i in v.node_items.values() if i.node.key == key]
def linked():
    g = pw.read_graph()
    a = {n.id for n in g.nodes.values() if n.app_name == APP}; d = {n.id for n in g.nodes.values() if n.name == MIC}
    return any(l.out_node in a and l.in_node in d for l in g.links)
AK, MK = f"app:{APP}", f"dev:{MIC}"

pw.create_virtual_mic("Selftest Ghost", MIC)
pa = start(); time.sleep(1.5)
w = m.MainWindow(); w.show(); wait(2500); v = w.view
a, mic = items(v, AK)[0], items(v, MK)[0]
w.connect_nodes(a, mic); wait(1200)
ok("app -> mic connected", linked())
row = items(v, AK)[0].pos().y()

stop(pa); wait(1500)
it = items(v, AK)
ok("App gone: card stays, greyed out", len(it) == 1 and it[0].ghost and it[0].opacity() < 0.5, [(i.ghost, i.opacity()) for i in it])
ok("…in the same place", it and it[0].pos().y() == row, (row, it and it[0].pos().y()))
ok("…without volume slider", it and not it[0].vol.isVisible())
pl = [x for x in v.wires if x.planned]
ok("saved route shown dashed", len(pl) == 1 and pl[0].src.node.key == AK and pl[0].dst.node.key == MK)
ok("status line does not count the ghost as a source", "source" in w.header.status.text(), w.header.status.text())
w.grab().save(str(OUT / "ghost.png"))

pa = start(); wait(2500)
it = items(v, AK)
ok("App back: normal card", len(it) == 1 and not it[0].ghost and it[0].opacity() == 1.0)
ok("…in the same place", it and it[0].pos().y() == row)
ok("…route restored automatically", linked())
ok("…no dashed wire any more", not [x for x in v.wires if x.planned])

stop(pa); wait(1500); w.close()
w = m.MainWindow(); w.show(); wait(2500); v = w.view
it = items(v, AK)
ok("Program restart: ghost is kept", len(it) == 1 and it[0].ghost and it[0].pos().y() == row)
v.delete_wire([x for x in v.wires if x.planned][0]); wait(800)
ok("disconnecting a dashed route removes the route", [AK, MK] not in w.cfg.routes and not [x for x in v.wires if x.planned])
w.connect_nodes(items(v, AK)[0], items(v, MK)[0]); wait(800)
ok("connecting ghost -> mic saves the route", [AK, MK] in w.cfg.routes and len([x for x in v.wires if x.planned]) == 1)
pa = start(); wait(2500)
ok("…and app start creates the link", linked())
stop(pa); wait(1500)
w.forget_node(AK); wait(800)
ok("\"Remove from list\": card gone", not items(v, AK))
cfg = json.loads(m.CONFIG.read_text())
ok("…route stays saved, key forgotten", [AK, MK] in cfg["routes"] and AK not in cfg["known_nodes"] and AK not in cfg["order"]["left"])
pa = start(); wait(2500)
ok("App returns: shown normally, route applies", items(v, AK) and not items(v, AK)[0].ghost and linked())
stop(pa); w.close()
pw.remove_virtual_mic(MIC); m.CONFIG.unlink(missing_ok=True)
finish(fails)
