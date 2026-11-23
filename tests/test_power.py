# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""On/off button. Test objects only, temp config."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (also sets sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtCore import Qt, QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import main as m, pw_backend as pw, fx as fxlib

m.CONFIG = OUT / "power_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0
MIC, TONE, APP = "diy_selftest_fxmic", "diy_selftest_tone", "diy_selftest_app"
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
def until(cond, ms=6000):
    e = time.time() + ms / 1000
    while time.time() < e:
        app.processEvents()
        if cond(): return True
        time.sleep(0.05)
    return cond()
def links(src_pred, dst_pred):
    g = pw.read_graph()
    return [l for l in g.links if g.nodes.get(l.out_node) and g.nodes.get(l.in_node)
            and src_pred(g.nodes[l.out_node]) and dst_pred(g.nodes[l.in_node])]
is_tone = lambda n: n.app_name == TONE
is_app = lambda n: n.app_name == APP
is_spk = lambda n: n.media_class == "Audio/Sink"
is_fx_in = lambda n: n.is_fx_in
is_fx_out = lambda n: n.is_fx_out
is_mic = lambda n: n.name == MIC

pw.create_virtual_mic("Selftest FX Mic", MIC)
tone = subprocess.Popen(["pw-play", "-P", f"{{ node.autoconnect = false node.name = {TONE} application.name = {TONE} }}", str(wav_file("tone40.wav"))],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
silent = subprocess.Popen(["pacat", "--playback", "--raw", "--format=s16le", "--rate=48000", "--channels=2",
                           f"--client-name={APP}", "/dev/zero"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)
w = m.MainWindow(); w.show(); w.resize(1100, 760); wait(2500); v = w.view
w.add_effect("highpass", QPointF(v.grid_span()[0] + 150, 120))
ok("high-pass running", until(lambda: any(i.running for i in v.fx_items.values()), 6000))
hp = next(iter(v.fx_items.values()))
item = lambda pred: next(i for i in v.node_items.values() if pred(i.node))
w.connect_nodes(item(is_tone), hp); wait(600); w.connect_nodes(hp, item(is_mic)); wait(800)
app_it = item(is_app)
spk_wire = [x for x in v.wires if x.src is app_it and is_spk(x.dst.node)]
ok("test app is on the speaker (WirePlumber)", spk_wire)
v.delete_wire(spk_wire[0]); wait(1000)
ok("initial state: route active, app→speaker blocked",
   links(is_tone, is_fx_in) and links(is_fx_out, is_mic) and not links(is_app, is_spk))

# --- switch off with the button
QTest.mouseClick(w.header.power_button, Qt.LeftButton); wait(2000)
ok("button shows \"Disabled\"", w.header.power_button.isChecked() and "Disabled" in w.header.power_button.text())
ok("routes disconnected", not links(is_tone, is_fx_in) and not links(is_fx_out, is_mic))
ok("effect stopped", until(lambda: fxlib.running_pid(hp.fx["id"]) is None, 4000))
ok("blocked app plays through the default speaker again", len(links(is_app, is_spk)) == 2)
ok("virtual mic stays", any(n.name == MIC for n in pw.read_graph().nodes.values()))
ok("editing locked, status shows disabled", not v.isInteractive() and "disabled" in w.header.status.text())
ok("state saved", json.loads(m.CONFIG.read_text())["disabled"] is True)
wait(2500)
ok("stays off (nothing reconnected/restarted)", not links(is_tone, is_fx_in) and fxlib.running_pid(hp.fx["id"]) is None)
w.grab().save(str(OUT / "power_off.png"))

# --- restart while disabled
w.close(); wait(400)
w = m.MainWindow(); w.show(); w.resize(1100, 760); wait(3000); v = w.view
ok("restart: stays disabled", w.header.power_button.isChecked() and not v.isInteractive()
   and not links(is_tone, is_fx_in) and fxlib.running_pid(hp.fx["id"]) is None)

# --- switch on
QTest.mouseClick(w.header.power_button, Qt.LeftButton); wait(500)
ok("button shows \"Active\"", not w.header.power_button.isChecked() and "Active" in w.header.power_button.text())
ok("effect starts again", until(lambda: fxlib.running_pid(hp.fx["id"]) is not None and any(i.running for i in w.view.fx_items.values()), 8000))
ok("routes restored", until(lambda: links(is_tone, is_fx_in) and links(is_fx_out, is_mic), 6000))
ok("block applies again (app not on the speaker)", until(lambda: not links(is_app, is_spk), 4000))
ok("editing possible again", v.isInteractive() and json.loads(m.CONFIG.read_text())["disabled"] is False)

for it in list(v.fx_items.values()): w.remove_effect(it)
until(lambda: fxlib.running_pid(hp.fx["id"]) is None, 5000)
w.close(); tone.kill(); silent.kill()
pw.remove_virtual_mic(MIC); m.CONFIG.unlink(missing_ok=True)
finish(fails)
