# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Ignore list: test app hidden, stays hidden when it plays again, persistent, undo via menu."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (also sets sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtWidgets import QApplication
import main as m

m.CONFIG = OUT / "ignore_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0; APP = "diy_selftest_app"; AK = f"app:{APP}"
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
def start():
    return subprocess.Popen(["pacat", "--playback", "--raw", "--format=s16le", "--rate=48000", "--channels=2",
                             f"--client-name={APP}", "/dev/zero"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def items(v): return [i for i in v.node_items.values() if i.node.key == AK]
def nsrc(w): return w.header.status.text().split("·")[1].strip()

pa = start(); time.sleep(1.5)
w = m.MainWindow(); w.show(); wait(2500); v = w.view
ok("Test-App sichtbar", items(v)); before = nsrc(w)
w.ignore_node(items(v)[0]); wait(1000)
ok("ignore hides it", not items(v))
ok("…and no wires any more", not [x for x in v.wires if x.src.node.key == AK])
ok("status line no longer counts it", nsrc(w) != before, (before, nsrc(w)))
pa.terminate(); pa.wait(); wait(1200)
ok("app ended: no greyed-out card either", not items(v))
pa = start(); wait(2500)
ok("app plays again: stays hidden", not items(v))
cfg = json.loads(m.CONFIG.read_text())
ok("saved in config", AK in cfg["ignored"] and AK not in cfg["order"]["left"], cfg["ignored"])
w.close()
w = m.MainWindow(); w.show(); wait(2500); v = w.view
ok("program restart: stays hidden", not items(v))
w.header._fill_hidden(w)
acts = [a.text() for a in w.header.hidden_menu.actions() if a.text()]
ok("⋯ → Hidden lists the app", any(APP in t for t in acts), acts)
[a for a in w.header.hidden_menu.actions() if APP in a.text()][0].trigger(); wait(1500)
ok("\"show again\" shows it again", items(v) and not items(v)[0].ghost)
pa.terminate(); pa.wait(); wait(1200)
ok("…afterwards greyed out normally again when paused", items(v) and items(v)[0].ghost)
w.ignore_node(items(v)[0]); wait(800)
ok("ignore a greyed-out card", not items(v) and AK in w.cfg.ignored)
w.close(); m.CONFIG.unlink(missing_ok=True)
finish(fails)
