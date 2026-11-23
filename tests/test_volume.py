# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""Volume slider test on test objects only (diy_selftest_vol mic + diy_selftest_app stream)."""
import re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (also sets sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import main as m, pw_backend as pw

m.CONFIG = OUT / "vol_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
def wp(nid):
    out = subprocess.run(["wpctl", "get-volume", str(nid)], capture_output=True, text=True).stdout
    v = float(re.search(r"Volume: ([\d.]+)", out).group(1)); return v, "MUTED" in out

real_before = {n.id: (round(n.volume, 3), n.mute) for n in pw.read_graph().nodes.values() if not n.name.startswith("diy_selftest")}
pw.create_virtual_mic("Selftest Vol", "diy_selftest_vol")
pa = subprocess.Popen(["pacat", "--playback", "--raw", "--format=s16le", "--rate=48000", "--channels=2",
                       "--client-name=diy_selftest_app", "/dev/zero"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)
w = m.MainWindow(); w.show(); w.resize(1000, 760); wait(2500); v = w.view; vp = v.viewport()
it = [i for i in v.node_items.values() if i.node.name == "diy_selftest_vol"][0]
ap = [i for i in v.node_items.values() if i.node.app_name == "diy_selftest_app"][0]
ok("slider visible (mic, app, all devices)", all(i.vol.isVisible() for i in v.node_items.values()),
   [(i.node.label, i.vol.isVisible()) for i in v.node_items.values()])
for i in v.node_items.values():
    if not i.node.name.startswith("diy_selftest") and not i.node.app_name.startswith("diy_selftest"):
        ok(f"display = wpctl for {i.node.label!r}", (round(i.vol.value, 2), i.vol.muted) == (round(wp(i.node.id)[0], 2), wp(i.node.id)[1]),
           (round(i.vol.value, 2), i.vol.muted, wp(i.node.id)))

def at(item, v_):   # viewport point for a value on item's track
    return v.mapFromScene(item.vol.mapToScene(QPointF(item.vol._x_for(v_), item.vol.Y + item.vol.H / 2)))

y_before = it.pos().y()
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, at(it, 1.0)); wait(50)
for k in range(1, 11):
    QTest.mouseMove(vp, at(it, 1.0 - 0.05 * k)); wait(30)
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, at(it, 0.5)); wait(600)
ok("dragging sets the mic to ~50 %", abs(wp(it.node.id)[0] - 0.5) < 0.03, wp(it.node.id))
ok("dragging the slider does not move the card", it.pos().y() == y_before)
ok("display follows", abs(it.vol.value - 0.5) < 0.03, it.vol.value)

QApplication.sendEvent(vp, QWheelEvent(QPointF(at(it, 0.5)), QPointF(vp.mapToGlobal(at(it, 0.5))), QPoint(0, 0), QPoint(0, 120),
                                       Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)); wait(600)
ok("mouse wheel +5 %", abs(wp(it.node.id)[0] - 0.55) < 0.02, wp(it.node.id))

mp = v.mapFromScene(it.vol.mapToScene(it.vol.mute_rect().center()))
m0 = wp(it.node.id)[1]
ok("muted display = wpctl before click", it.vol.muted == m0, (it.vol.muted, m0))
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, mp); wait(600)
ok("mute button toggles", wp(it.node.id)[1] is (not m0) and it.vol.muted is (not m0))
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, mp); wait(600)
ok("…and back", wp(it.node.id)[1] is m0 and it.vol.muted is m0)
pw.set_mute(it.node.id, False); wait(1600)
ok("display follows external unmute", it.vol.muted is False)

pt = QPointF(at(it, 0.3)); gp = QPointF(vp.mapToGlobal(at(it, 0.3)))
for t, b in ((QEvent.MouseButtonPress, Qt.LeftButton), (QEvent.MouseButtonRelease, Qt.NoButton),
             (QEvent.MouseButtonPress, Qt.LeftButton), (QEvent.MouseButtonDblClick, Qt.LeftButton),
             (QEvent.MouseButtonRelease, Qt.NoButton)):
    QApplication.sendEvent(vp, QMouseEvent(t, pt, gp, Qt.LeftButton, b, Qt.NoModifier)); app.processEvents()
wait(600)
ok("double-click -> 100 %", abs(wp(it.node.id)[0] - 1.0) < 0.01, wp(it.node.id))

QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, at(ap, 1.0)); wait(50)
QTest.mouseMove(vp, at(ap, 1.3)); wait(50)
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, at(ap, 1.3)); wait(600)
ok("app stream above 100 % (130 %)", abs(wp(ap.node.id)[0] - 1.3) < 0.03, wp(ap.node.id))

subprocess.run(["wpctl", "set-volume", str(it.node.id), "0.25"]); wait(1800)
ok("external change (wpctl) shows in the slider", abs(it.vol.value - 0.25) < 0.02, it.vol.value)
w.grab().save(str(OUT / "volume.png"))
w.close(); pa.terminate(); pa.wait()
pw.remove_virtual_mic("diy_selftest_vol"); m.CONFIG.unlink(missing_ok=True)
real_after = {n.id: (round(n.volume, 3), n.mute) for n in pw.read_graph().nodes.values() if n.id in real_before}
ok("real devices unchanged", real_after == real_before, (real_before, real_after))
finish(fails)
