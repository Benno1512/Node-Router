# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""Tests the two sortable lists in a real window with a temp config."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (also sets sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import main as m, pw_backend as pw

m.CONFIG = OUT / "order_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
def col(view, side):
    return [(round(i.pos().x()), round(i.pos().y()), i.node.label)
            for i in sorted(view.node_items.values(), key=lambda i: i.pos().y()) if i.side == side]

pw.create_virtual_mic("Selftest A", "diy_selftest_a"); pw.create_virtual_mic("Selftest B", "diy_selftest_b")
w = m.MainWindow(); w.show(); wait(2500); v = w.view
L, R = col(v, "left"), col(v, "right")
print("left:", L); print("right:", R)
ok("left column fixed x, rows without gaps", all(x == m.LEFT_X for x, *_ in L) and [y for _, y, _ in L] == [m.TOP + i * m.ROW for i in range(len(L))])
ok("right column fixed x, rows without gaps", all(x == round(v.col_x("right")) for x, *_ in R) and [y for _, y, _ in R] == [m.TOP + i * m.ROW for i in range(len(R))])

# drag the last right entry diagonally upwards -> should land at slot 0, x stays
last = sorted([i for i in v.node_items.values() if i.side == "right"], key=lambda i: i.pos().y())[-1]
label = last.node.label
c = v.mapFromScene(last.sceneBoundingRect().center())
vp = v.viewport()
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, c); wait(50)
for t in range(1, 16):
    QTest.mouseMove(vp, c + QPoint(-15 * t, -int(len(R) * m.ROW * t / 15) - 10 * t)); wait(20)
ok("while dragging: x stays in the column", round(last.pos().x()) == round(v.col_x("right")), last.pos())
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, c + QPoint(-225, -len(R) * m.ROW - 150)); wait(500)
R2 = col(v, "right"); print("right afterwards:", R2)
ok("sorted to the top", R2[0][2] == label and [y for _, y, _ in R2] == [m.TOP + i * m.ROW for i in range(len(R2))])
order = json.loads(m.CONFIG.read_text())["order"]
ok("order saved", order["right"][0] == last.node.key, order["right"])
ok("wire end points follow", all(abs(wi.path().pointAtPercent(1).y() - wi.dst.port.scene_center().y()) < 1 for wi in v.wires))
vw = v.viewport().width()
ok("right list flush with the right edge", round(v.col_x("right")) + m.NODE_W + m.MARGIN == vw, (v.col_x("right"), vw))
ok("left list flush with the left edge", round(L[0][0]) == m.MARGIN)
ok("no horizontal scroll bar", not v.horizontalScrollBar().isVisible())
t0 = v.transform().m11()
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
from PySide6.QtGui import QWheelEvent
from PySide6.QtCore import QPointF
for _ in range(5):
    QApplication.sendEvent(vp, QWheelEvent(QPointF(400, 300), QPointF(v.mapToGlobal(QPoint(400, 300))), QPoint(0, 0), QPoint(0, 120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
wait(200)
ok("mouse wheel does not zoom", v.transform().m11() == t0 == 1.0, v.transform().m11())
ok("scene = window width", round(v.scene_.sceneRect().width()) == vw and v.scene_.sceneRect().left() == 0)
w.grab().save(str(OUT / "fixed_1000.png"))
w.resize(1400, 600); wait(500)
vw = v.viewport().width()
ok("after enlarging: right list moves along", all(round(i.pos().x()) + m.NODE_W + m.MARGIN == vw for i in v.node_items.values() if i.side == "right"))
ok("wires follow on resize", all(abs(wi.path().pointAtPercent(1).x() - wi.dst.port.scene_center().x()) < 1 for wi in v.wires))
w.grab().save(str(OUT / "fixed_1400.png"))
w.resize(640, 400); wait(500)
ok("minimum width: lists do not overlap", v.col_x("right") > m.LEFT_X + m.NODE_W, (w.width(), v.col_x("right")))
w.close()

# restart -> order stays; remove and re-create mic B -> same slot
w = m.MainWindow(); w.show(); wait(2500)
ok("restart: order kept", col(w.view, "right") == R2, col(w.view, "right"))
pw.remove_virtual_mic("diy_selftest_b"); wait(1500)
pw.create_virtual_mic("Selftest B", "diy_selftest_b"); wait(2000)
ok("node disappears/returns: same slot", col(w.view, "right") == R2, col(w.view, "right"))
w.close()
for n in ("diy_selftest_a", "diy_selftest_b"): pw.remove_virtual_mic(n)
m.CONFIG.unlink(missing_ok=True)
finish(fails)
