# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Blocked routes: WP link app->speaker disconnected, app restart -> link removed again."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (setzt auch sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtWidgets import QApplication
import main as m, pw_backend as pw

m.CONFIG = OUT / "blocked_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0; APP = "diy_selftest_app"
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
def start():
    return subprocess.Popen(["pacat", "--playback", "--raw", "--format=s16le", "--rate=48000", "--channels=2",
                             f"--client-name={APP}", "/dev/zero"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def to_sink():
    g = pw.read_graph()
    a = {n.id for n in g.nodes.values() if n.app_name == APP}
    s = {n.id for n in g.nodes.values() if n.media_class == "Audio/Sink"}
    return [l for l in g.links if l.out_node in a and l.in_node in s]

p = start(); time.sleep(1.5)
ok("WP verbindet Test-App mit Lautsprecher", len(to_sink()) == 2)
w = m.MainWindow(); w.show(); wait(2500); v = w.view
wire = [x for x in v.wires if x.src.node.app_name == APP and x.dst.node.media_class == "Audio/Sink"]
ok("Wire sichtbar", wire)
v.delete_wire(wire[0]); wait(1200)
ok("Trennen entfernt WP-Link", not to_sink())
key = [f"app:{APP}", "dev:" + wire[0].dst.node.name]
ok("als blockiert gespeichert", key in json.loads(m.CONFIG.read_text())["blocked"])
p.terminate(); p.wait(); wait(1200)
ok("App weg: Ghost ohne gestrichelten Wire zur blockierten Senke",
   not [x for x in v.wires if x.planned and x.dst.node.media_class == "Audio/Sink"])
p = start(); t0 = time.time(); seen = None
while time.time() - t0 < 5:
    wait(100)
    if to_sink(): seen = seen or time.time()
    elif seen: break
ok("App-Neustart: WP-Link wieder entfernt", seen and not to_sink(),
   f"{(time.time() - seen) * 1000:.0f} ms" if seen else "WP hat nicht neu verbunden?")
wait(1500); ok("…bleibt weg", not to_sink())
appn = [i for i in v.node_items.values() if i.node.app_name == APP and not i.ghost][0]
sink = [i for i in v.node_items.values() if i.node.media_class == "Audio/Sink"][0]
w.connect_nodes(appn, sink); wait(1200)
cfg = json.loads(m.CONFIG.read_text())
ok("wieder verbinden hebt Block auf", len(to_sink()) == 2 and key not in cfg["blocked"] and key in cfg["routes"])
p.terminate(); p.wait(); wait(800); p = start(); wait(2500)
ok("App-Neustart danach: Link bleibt", len(to_sink()) == 2)
w.close(); p.terminate(); p.wait(); m.CONFIG.unlink(missing_ok=True)
finish(fails)
