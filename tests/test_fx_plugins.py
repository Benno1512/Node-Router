# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Noise suppression, compressor, ducking (2 inputs) in the real window. Temp config, silent."""
import json, math, random, struct, subprocess, sys, time, wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (also sets sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu
import main as m, pw_backend as pw, fx as fxlib

missing = [fxlib.available(k)[1] for k in ("denoise", "compressor", "duck") if not fxlib.available(k)[0]]
if missing:
    print("SKIP:", "; ".join(missing)); sys.exit(SKIP)
m.CONFIG = OUT / "fx2_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0
MIC, TONE, NOISE = "diy_selftest_fxmic", "diy_selftest_tone", "diy_selftest_noise"
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

tone_f = wav_file("tone40.wav")
noise_f = wav_file("noise40.wav")

def rms():
    rec = OUT / "rec.wav"; rec.unlink(missing_ok=True)
    subprocess.run(["timeout", "-s", "INT", "1.0", "pw-record", "--target", MIC, "--rate", "48000",
                    "--channels", "1", "--format", "s16", str(rec)], capture_output=True)
    try:
        w = wave.open(str(rec)); s = struct.unpack("<%dh" % w.getnframes(), w.readframes(w.getnframes()))
    except Exception:
        return -1
    s = s[len(s) // 3:]
    return math.sqrt(sum(x * x for x in s) / max(1, len(s)))
def db(a, b): return 20 * math.log10(max(a, 1) / max(b, 1))
def player(name, f):
    return subprocess.Popen(["pw-play", "-P", f"{{ node.autoconnect = false node.name = {name} application.name = {name} }}", str(f)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

pw.create_virtual_mic("Selftest FX Mic", MIC)
pt, pn = player(TONE, tone_f), player(NOISE, noise_f)
time.sleep(1.0)
w = m.MainWindow(); w.show(); w.resize(1200, 900); wait(2500); v = w.view; vp = v.viewport()
item = lambda pred: next(i for i in v.node_items.values() if pred(i.node))
tone_it = item(lambda n: n.app_name == TONE); noise_it = item(lambda n: n.app_name == NOISE); mic_it = item(lambda n: n.name == MIC)
P = lambda port: v.mapFromScene(port.scene_center())
def drag(a, b):
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, a); wait(30)
    for k in range(1, 9): QTest.mouseMove(vp, a + (b - a) * k / 8); wait(15)
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, b); wait(900)
def direct(src_port):            # reference: source straight into the mic
    drag(P(src_port), P(mic_it.port)); r = rms()
    wi = [x for x in v.wires if x.dst is mic_it and x.src is src_port.node_item][0]; v.delete_wire(wi); wait(700)
    return r

# menu
picked = []
class FakeMenu(QMenu):
    def exec(self, *a):
        picked.append([(x.text(), x.isEnabled()) for x in self.actions() if x.text()])
        for x in self.actions():
            if x.text() == want[0]: x.trigger()
orig = m.QMenu; m.QMenu = FakeMenu
gl, gr = v.grid_span()
from PySide6.QtCore import QEvent
from PySide6.QtGui import QMouseEvent
for title, (x, y) in {"Noise suppression": (gl + 140, 60), "Compressor": (gl + 140, 300), "Ducking": (gr - 140, 160)}.items():
    want = [title]; pt_ = v.mapFromScene(QPointF(x, y))
    QApplication.sendEvent(vp, QMouseEvent(QEvent.MouseButtonDblClick, QPointF(pt_), QPointF(vp.mapToGlobal(pt_)),
                                           Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)); wait(200)
m.QMenu = orig
ok("menu: 7 blocks, all available", picked and len([t for t in picked[0] if t[0] != "Add block"]) == 7
   and all(e for t, e in picked[0] if t != "Add block"), picked[:1])
ok("3 new blocks running", until(lambda: len(v.fx_items) == 3 and all(i.running for i in v.fx_items.values()), 8000),
   [(i.spec["title"], i.running) for i in v.fx_items.values()])
fx = {i.spec["title"]: i for i in v.fx_items.values()}
dn, cp, dk = fx["Noise suppression"], fx["Compressor"], fx["Ducking"]
ok("ducking card has 2 inputs", len(dk.in_ports) == 2 and set(dk.in_ports) == {"main", "prio"})

ref_tone, ref_noise = direct(tone_it.port), direct(noise_it.port)
print(f"   direct reference: tone {ref_tone:.0f}, noise {ref_noise:.0f}")

# noise suppression
drag(P(noise_it.port), P(dn.in_port)); drag(P(dn.out_port), P(mic_it.port))
r = rms(); ok("noise suppression removes noise", 0 <= r and db(r, ref_noise) < -30, f"{db(r, ref_noise):+.1f} dB")
for x in list(dn.wires): v.delete_wire(x); wait(200)
wait(600)

# compressor (threshold -30, 10:1)
w.set_effect_param(cp, "thresh", -30, True); w.set_effect_param(cp, "ratio", 10, True)
drag(P(tone_it.port), P(cp.in_port)); drag(P(cp.out_port), P(mic_it.port))
r = rms(); ok("compressor lowers a loud tone", db(r, ref_tone) < -10, f"{db(r, ref_tone):+.1f} dB")
for x in list(cp.wires): v.delete_wire(x); wait(200)
wait(600)

# Ducking: tone = music (dropped on the card near the upper input), noise = priority (port)
up = dk.in_ports["main"]; low = dk.in_ports["prio"]
drag(P(tone_it.port), v.mapFromScene(up.scene_center() + QPointF(60, 0)))
drag(P(noise_it.port), P(low))
drag(P(dk.out_port), P(mic_it.port))
gw = {(x.src, x.group) for x in v.wires if x.dst is dk and not x.planned}
ok("wires at the right inputs", {(tone_it, "main"), (noise_it, "prio")} <= gw, gw)
g = pw.read_graph()
chans = {(g.nodes[l.out_node].app_name, g.in_channel(l)) for l in g.links if g.nodes.get(l.in_node) and g.nodes[l.in_node].name.endswith(dk.fx["id"] + "_in")}
ok("PipeWire: music→FL/FR, priority→RL/RR", chans == {(TONE, "FL"), (TONE, "FR"), (NOISE, "RL"), (NOISE, "RR")}, chans)
r_duck = rms()
v.delete_wire([x for x in v.wires if x.dst is dk and x.group == "prio"][0]); wait(1500)
r_free = rms()
ok("ducking: music quieter while priority is present", db(r_duck, r_free) < -6, f"with prio {db(r_duck, r_free):+.1f} dB")
ok("ducking without priority: music unchanged", abs(db(r_free, ref_tone)) < 1.5, f"{db(r_free, ref_tone):+.1f} dB")
ok("disconnecting priority leaves the music wire", any(x.src is tone_it and x.dst is dk and x.group == "main" for x in v.wires))
drag(P(noise_it.port), P(low))
routes = json.loads(m.CONFIG.read_text())["routes"]
ok("routes saved with input group", any(r[1].endswith("#prio") for r in routes) and any(r[1].endswith("#main") for r in routes), routes)
w.grab().save(str(OUT / "fx2_window.png"))

# program restart + prio app restart
w.close(); wait(400)
w = m.MainWindow(); w.show(); w.resize(1200, 900); wait(3000); v = w.view
dk = next(i for i in v.fx_items.values() if i.spec["title"] == "Ducking")
noise_it = item(lambda n: n.app_name == NOISE)
ok("restart: wires at the right inputs", {x.group for x in v.wires if x.dst is dk and not x.planned} == {"main", "prio"})
pn.kill(); pn.wait(); wait(1200)
ok("prio app gone: dashed at the prio input", any(x.planned and x.dst is dk and x.group == "prio" for x in v.wires))
pn = player(NOISE, noise_f); wait(3000)
g = pw.read_graph()
chans = {g.in_channel(l) for l in g.links if g.nodes.get(l.out_node) and g.nodes[l.out_node].app_name == NOISE
         and g.nodes.get(l.in_node) and g.nodes[l.in_node].is_effect}       # not the level meter
ok("prio app back: route on RL/RR again", chans == {"RL", "RR"}, chans)

ids = [it.fx["id"] for it in v.fx_items.values()]
for it in list(v.fx_items.values()): w.remove_effect(it)
ok("remove: processes ended", until(lambda: all(fxlib.running_pid(i) is None for i in ids), 5000))
w.close(); pt.kill(); pn.kill()
pw.remove_virtual_mic(MIC); m.CONFIG.unlink(missing_ok=True)
finish(fails)
