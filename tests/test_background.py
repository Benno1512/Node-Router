# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Background operation: tray, autostart toggle, single instance, restart of the
PipeWire monitor, re-creating virtual mics after they are lost.
Simulates a PipeWire restart (ending the monitor process, unloading the mic module),
without restarting PipeWire itself."""
import json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish  # noqa: E402
from PySide6.QtCore import QProcess  # noqa: E402
from PySide6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

os.environ["XDG_CONFIG_HOME"] = str(OUT / "xdg_config")      # autostart only in the temp folder
import main as m, pw_backend as pw  # noqa: E402

m.CONFIG = OUT / "bg_config.json"; m.CONFIG.unlink(missing_ok=True)
VM = "diy_selftest_vmre"
m.CONFIG.write_text(json.dumps({"virtual_mics": [{"name": VM, "label": "Selftest VM Re"}]}))
app = QApplication([]); fails = 0
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
def vm_present():
    return any(n.name == VM for n in pw.read_graph().nodes.values())

# --- Tray: closing only hides, the router keeps working
if not QSystemTrayIcon.isSystemTrayAvailable():
    print("SKIP: no system tray available"); pw.remove_virtual_mic(VM); sys.exit(SKIP)
w = m.MainWindow(tray=True); w.show(); wait(2000)
ok("virtual mic from config created", until(vm_present, 4000))
ok("tray icon visible", w.tray is not None and w.tray.isVisible())
w.close(); wait(300)
ok("Closing hides to the tray", not w.isVisible() and not w._shutting)
n0 = len(w.graph.nodes); w.graph = m.pw.Graph({}, []); w.refresh(force=True)
ok("…and keeps working (reads graph)", until(lambda: w.proc.state() == QProcess.NotRunning and w.graph.nodes, 3000), n0)
w.show_window(); wait(200)
ok("Tray → Open window", w.isVisible())

# --- autostart toggle
af = m.autostart_file()
w.header.autostart_action.setChecked(True); wait(100)
txt = af.read_text() if af.exists() else ""
ok("autostart entry created (minimized, this installation)",
   af.exists() and "--minimized" in txt and str(m.MAIN) in txt and sys.executable in txt and "icon.svg" in txt, af)
w.header.autostart_action.setChecked(False); wait(100)
ok("Autostart entry removed", not af.exists())

# --- simulate a PipeWire restart: monitor ends
w.mon.kill(); w.mon.waitForFinished(1000)
ok("Monitor restarts after it ends", until(lambda: w.mon.state() == QProcess.Running, 4000))
mid = [l.split("\t")[0] for l in subprocess.run(["pactl", "list", "short", "modules"], capture_output=True, text=True).stdout.splitlines()
       if f"sink_name={VM}" in l]
subprocess.run(["pactl", "unload-module", mid[0]], capture_output=True)
ok("virtual mic gone (simulated)", until(lambda: not vm_present(), 3000))
ok("…is re-created automatically", until(vm_present, 9000))

# --- disabled: mics are still looked after
w.set_router_disabled(True); wait(300)
ok("Tray menu follows on/off", not w.tray_active.isChecked())
w.tray_active.setChecked(True); wait(300)
ok("Tray menu turns the router back on", not w.cfg.disabled and not w.header.power_button.isChecked())

w.quit_app(); wait(300)
ok("Quit really closes", w._shutting and not w.tray.isVisible())

# --- single instance (real processes, own config, own XDG)
env = dict(os.environ, DIY_ROUTER_CONFIG=str(OUT / "bg_single.json"))
first = subprocess.Popen([sys.executable, str(NR / "main.py"), "--minimized"], cwd=NR, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(3)
ok("first instance running (minimized)", first.poll() is None)
t0 = time.time()
second = subprocess.run([sys.executable, str(NR / "main.py")], cwd=NR, env=env, capture_output=True, text=True, timeout=20)
ok("second instance exits immediately", second.returncode == 0 and "already running" in second.stderr and time.time() - t0 < 10,
   (second.returncode, second.stderr.strip()[-80:]))
ok("first instance keeps running", first.poll() is None)
first.terminate()
try: first.wait(5)
except subprocess.TimeoutExpired: first.kill()
third = subprocess.Popen([sys.executable, str(NR / "main.py"), "--minimized"], cwd=NR, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)
ok("after the first one ends/crashes a new one starts normally", third.poll() is None)
third.terminate()
try: third.wait(5)
except subprocess.TimeoutExpired: third.kill()

pw.remove_virtual_mic(VM)
for f in ("bg_config.json", "bg_single.json"): (OUT / f).unlink(missing_ok=True)
finish(fails)
