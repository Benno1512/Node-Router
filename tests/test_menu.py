# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (setzt auch sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu
import main as m, fx as fxlib

m.CONFIG = OUT / "menu_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
orig_avail = fxlib.available
fxlib.available = lambda k: (False, fxlib.TYPES[k]["missing"]) if k == "compressor" else orig_avail(k)
w = m.MainWindow(); w.show(); w.resize(1100, 700); wait(1500); v = w.view
added = []
w.add_effect = lambda k, sp: added.append(k)
def open_menu():
    menu = QMenu(v); v.add_menu(menu, v.mapFromScene(QPointF(v.grid_span()[0] + 100, 100)))
    menu.popup(v.mapToGlobal(QPoint(400, 120))); wait(400); return menu
menu = open_menu()
entries = {a.text(): a.defaultWidget() for a in menu.actions() if a.text()}
ok("7 Einträge mit Beschreibung", len(entries) == 7 and all(e.findChild(m.QLabel, "FxDesc").text() for e in entries.values()))
for name in ("Hochpass", "Equalizer", "Delay"):
    QTest.mouseMove(entries[name], QPoint(40, 15)); wait(900)
    tips = [x for x in app.topLevelWidgets() if x.metaObject().className() == "QTipLabel" and x.isVisible()]
    ok(f"Hover {name}: hervorgehoben, kein Tooltip", entries[name].underMouse() and not tips)
    if name == "Equalizer":
        menu.grab().save(str(OUT / "menu_dark.png"))
comp = entries["Kompressor"]
ok("fehlendes Plugin: ausgegraut + Grund", not comp.isEnabled() and "lsp-plugins" in comp.findChild(m.QLabel, "FxDesc").text())
QTest.mouseClick(comp, Qt.LeftButton, Qt.NoModifier, QPoint(40, 15)); wait(200)
ok("…Klick darauf bewirkt nichts", added == [] and menu.isVisible())
QTest.mouseRelease(entries["Ducking"], Qt.LeftButton, Qt.NoModifier, QPoint(40, 15)); wait(200)
ok("Loslassen ohne Drücken (Rest vom Doppelklick) löst nichts aus", added == [] and menu.isVisible(), added)
QTest.mouseClick(entries["Delay"], Qt.LeftButton, Qt.NoModifier, QPoint(40, 15)); wait(200)
ok("Klick auf Delay legt Baustein an + schließt Menü", added == ["delay"] and not menu.isVisible(), added)
w.set_theme("light"); wait(300)
menu = open_menu()
QTest.mouseMove([a.defaultWidget() for a in menu.actions() if a.text() == "Hall"][0], QPoint(40, 15)); wait(500)
menu.grab().save(str(OUT / "menu_light.png")); menu.hide()
w.close(); m.CONFIG.unlink(missing_ok=True)
finish(fails)
