# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Theme test: render dark + light with test mic, test app, a ghost and wires; switching + persistence."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (also sets sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
import main as m, pw_backend as pw

m.CONFIG = OUT / "theme_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
def start(name):
    return subprocess.Popen(["pacat", "--playback", "--raw", "--format=s16le", "--rate=48000", "--channels=2",
                             f"--client-name={name}", "/dev/zero"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

pw.create_virtual_mic("Selftest Theme", "diy_selftest_theme")
p1, p2 = start("diy_selftest_app"), start("diy_selftest_ghostapp"); time.sleep(1.5)
w = m.MainWindow(); w.show(); w.resize(1000, 720); wait(2500); v = w.view
it = lambda key: [i for i in v.node_items.values() if i.node.key == key][0]
w.connect_nodes(it("app:diy_selftest_app"), it("dev:diy_selftest_theme"))
w.connect_nodes(it("app:diy_selftest_ghostapp"), it("dev:diy_selftest_theme")); wait(1200)
p2.terminate(); p2.wait(); wait(1500)
ok("ghost present", it("app:diy_selftest_ghostapp").ghost)
ok("default: dark", m.CURRENT_THEME == "dark" and w.cfg.theme == "dark")
w.grab().save(str(OUT / "theme_dark.png"))
w.header.theme_actions["light"].trigger(); wait(500)
ok("switch to light without restart", m.CURRENT_THEME == "light" and v.backgroundBrush().color().name() == m.PALETTES["light"]["bg"])
ok("light stylesheet", m.PALETTES["light"]["header"] in app.styleSheet())
ok("status line recolored", m.PALETTES["light"]["ok"] in w.header.status.text(), w.header.status.text()[:60])
w.grab().save(str(OUT / "theme_light.png"))
menu = w.header.more_button.menu()
menu.popup(w.header.more_button.mapToGlobal(QPoint(0, 40))); wait(300)
menu.grab().save(str(OUT / "theme_menu_light.png")); menu.hide()
ok("saved in config", json.loads(m.CONFIG.read_text())["theme"] == "light")
w.close()
w = m.MainWindow(); w.show(); wait(1500)
ok("restart: stays light, menu check mark correct", m.CURRENT_THEME == "light" and w.header.theme_actions["light"].isChecked())
w.header.theme_actions["system"].trigger(); wait(300)
ok("\"Follow system\" selectable", w.cfg.theme == "system", (w.cfg.theme, m.CURRENT_THEME))
w.header.theme_actions["dark"].trigger(); wait(300)
ok("back to dark", m.CURRENT_THEME == "dark" and m.PALETTES["dark"]["header"] in app.styleSheet())
w.close(); p1.terminate(); p1.wait()
pw.remove_virtual_mic("diy_selftest_theme"); m.CONFIG.unlink(missing_ok=True)
finish(fails)
