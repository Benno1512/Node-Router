# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – DIY Audio Router
"""Effect blocks end-to-end in the real window (temp config, test objects only, silent)."""
import json, math, os, struct, subprocess, sys, time, wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (setzt auch sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu
import main as m, pw_backend as pw, fx as fxlib

m.CONFIG = OUT / "fx_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0
MIC, TONE = "diy_selftest_fxmic", "diy_selftest_tone"
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

# 30 s Sinus 440 Hz
sine = wav_file("sine30.wav")
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

pw.create_virtual_mic("Selftest FX Mic", MIC)
tone = subprocess.Popen(["pw-play", "-P", f"{{ node.autoconnect = false node.name = {TONE} application.name = {TONE} }}", str(sine)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.0)
w = m.MainWindow(); w.show(); w.resize(1150, 800); wait(2500); v = w.view; vp = v.viewport()

# --- Doppelklick-Menü
picked = []
class FakeMenu(QMenu):
    def exec(self, *a):
        picked.append([x.text() for x in self.actions()])
        for x in self.actions():
            if x.text() == want[0]:
                x.trigger()
orig_menu = m.QMenu
m.QMenu = FakeMenu
gl, gr = v.grid_span()
spots = {"Hochpass": (gl + 140, 80), "Delay": (gl + 140, 330), "Equalizer": (gr - 140, 80), "Hall": (gr - 140, 330)}
for title, (x, y) in spots.items():
    want = [title]
    pt = v.mapFromScene(QPointF(x, y))
    QApplication.sendEvent(vp, QMouseEvent(QEvent.MouseButtonDblClick, QPointF(pt), QPointF(vp.mapToGlobal(pt)),
                                           Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)); wait(200)
m.QMenu = orig_menu
ok("Doppelklick-Menü listet die 4 Bausteine", picked and all(t in picked[0] for t in spots), picked[:1])
ok("4 Bausteine angelegt", len(w.cfg.effects) == 4 and len(v.fx_items) == 4)
ok("alle Prozesse laufen (Karten aktiv)", until(lambda: all(i.running for i in v.fx_items.values()), 8000),
   [(i.spec["title"], i.running) for i in v.fx_items.values()])
fx = {i.spec["title"]: i for i in v.fx_items.values()}
hp, dl, eq, rv = fx["Hochpass"], fx["Delay"], fx["Equalizer"], fx["Hall"]
ok("Effekt-Nodes erscheinen nicht in den Listen", not [i for i in v.node_items.values() if i.node.is_effect])

# --- frei verschieben
p0 = hp.pos()
c = v.mapFromScene(hp.mapToScene(QPointF(FX := 60, 12)))
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, c); wait(50)
for k in range(1, 9): QTest.mouseMove(vp, c + QPoint(10 * k, 15 * k)); wait(20)
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, c + QPoint(80, 120)); wait(300)
ok("frei verschiebbar (x und y)", abs(hp.pos().x() - p0.x() - 80) < 2 and abs(hp.pos().y() - p0.y() - 120) < 2, (p0, hp.pos()))
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v.mapFromScene(hp.mapToScene(QPointF(60, 12)))); wait(50)
QTest.mouseMove(vp, QPoint(5, 5)); wait(50); QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5)); wait(300)
lo, hi = v._fx_x_range()
ok("bleibt im Netz (nicht über die Listen)", abs(hp.pos().x() - lo) < 1 and hp.pos().y() >= 8, (hp.pos(), lo))
cfg_fx = {f["id"]: f for f in json.loads(m.CONFIG.read_text())["effects"]}
ok("Position gespeichert", cfg_fx[hp.fx["id"]]["x"] == 0.0)

# --- verbinden: Ton (Liste) -> Hochpass (auf Karte loslassen) -> Delay -> Test-Mikro (Port)
tone_it = [i for i in v.node_items.values() if i.node.app_name == TONE][0]
mic_it = [i for i in v.node_items.values() if i.node.name == MIC][0]
def drag(a, b):
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, a); wait(30)
    for k in range(1, 9): QTest.mouseMove(vp, a + (b - a) * k / 8); wait(15)
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, b); wait(900)
P = lambda port: v.mapFromScene(port.scene_center())
drag(P(tone_it.port), v.mapFromScene(hp.mapToScene(QPointF(100, 60))))
drag(P(hp.out_port), P(dl.in_port))
drag(P(dl.out_port), P(mic_it.port))
wires = {(x.src, x.dst) for x in v.wires if not x.planned}
ok("Verbindungen Liste→Effekt→Effekt→Ziel sichtbar", {(tone_it, hp), (hp, dl), (dl, mic_it)} <= wires)
r1 = rms(); ok("Ton kommt durch die Kette am Mikro an", r1 > 2000, f"RMS {r1:.0f}")
# Hochpass-Regler auf ~3 kHz ziehen
sl = hp.sliders["freq"]
a, b = sl.track()
drag_from = v.mapFromScene(sl.mapToScene(QPointF(a + (b - a) * sl._norm(sl.value), sl.H / 2)))
to = v.mapFromScene(sl.mapToScene(QPointF(b, sl.H / 2)))
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, drag_from); wait(30)
for k in range(1, 9): QTest.mouseMove(vp, drag_from + (to - drag_from) * k / 8); wait(30)
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, to); wait(400)
r2 = rms(); ok("Hochpass-Regler wirkt live (Max 1 kHz dämpft 440 Hz)", 0 <= r2 < r1 / 3, f"{sl.text()}: RMS {r1:.0f} -> {r2:.0f}")
ok("Karte bleibt beim Regler-Ziehen stehen", abs(hp.pos().x() - lo) < 1)
sl.mouseDoubleClickEvent(type("E", (), {"accept": lambda s: None})()); wait(400)
ok("Doppelklick Regler -> Standard 80 Hz", sl.value == 80 and rms() > 2000)

# --- Hall: Nachhall ändern -> Neustart, Verbindungen bleiben
drag(P(dl.out_port), P(rv.in_port)); drag(P(rv.out_port), P(mic_it.port))
pid0 = fxlib.running_pid(rv.fx["id"])
w.set_effect_param(rv, "decay", 3.0, final=True); wait(300)
ok("Hall startet neu", until(lambda: fxlib.running_pid(rv.fx["id"]) not in (None, pid0), 6000))
ok("…und ist danach wieder aktiv + verbunden", until(lambda: rv.running and any(x.src is rv and x.dst is mic_it and not x.planned for x in v.wires), 8000))
w.grab().save(str(OUT / "fx_window.png"))

# --- Programm-Neustart: Effekte laufen weiter, alles wiederhergestellt
pids = {i.fx["id"]: fxlib.running_pid(i.fx["id"]) for i in v.fx_items.values()}
w.close(); wait(500)
ok("nach Schließen laufen die Effekt-Prozesse weiter", all(fxlib.running_pid(k) == p for k, p in pids.items()))
w = m.MainWindow(); w.show(); w.resize(1150, 800); wait(3000); v = w.view
ok("Neustart: gleiche Prozesse, nicht doppelt gestartet", {i.fx["id"]: fxlib.running_pid(i.fx["id"]) for i in v.fx_items.values()} == pids)
fx2 = {i.spec["title"]: i for i in v.fx_items.values()}
ok("Neustart: Positionen + Wires wieder da", abs(fx2["Hochpass"].pos().x() - v._fx_x_range()[0]) < 1 and
   any(x.src is fx2["Hochpass"] and x.dst is fx2["Delay"] for x in v.wires))
ok("Neustart: Ton läuft weiter durch", rms() > 2000)

# --- entfernen
for it in list(v.fx_items.values()):
    w.remove_effect(it)
ok("Entfernen: Prozesse beendet", until(lambda: all(fxlib.running_pid(k) is None for k in pids), 5000))
wait(800)
own = [p for p in fxlib.FX_DIR.glob("*") if p.name.split(".")[0].split("_")[0] in pids]   # nur eigene Bausteine
ok("Entfernen: Karten, Dateien, Routen weg", not v.fx_items and not own and
   not [r for r in w.cfg.routes if any(k.startswith("fx:") for k in r)], (own, w.cfg.routes))
ok("System-filter-chain unberührt", subprocess.run(["pgrep", "-f", "pipewire -c filter-chain.conf"], capture_output=True).returncode == 0)
w.close(); tone.terminate(); tone.wait()
pw.remove_virtual_mic(MIC); m.CONFIG.unlink(missing_ok=True)
finish(fails)
