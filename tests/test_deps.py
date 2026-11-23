# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""System check (deps.py), notice dialog at start, bundled plugins incl. the
libatomic fallback for RNNoise (real effect process, test IDs only)."""
import ctypes.util, json, os, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, finish  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
import deps, fx as fxlib, main as m, pw_backend as pw  # noqa: E402

fails = 0
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)

# --- distro detection
cases = {"ubuntu": ('ID=ubuntu\nID_LIKE=debian\n', "apt"), "mint": ('ID=linuxmint\nID_LIKE="ubuntu debian"\n', "apt"),
         "fedora": ('ID=fedora\n', "dnf"), "manjaro": ('ID=manjaro\nID_LIKE=arch\n', "pacman"),
         "tumbleweed": ('ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n', "zypper"), "gentoo": ('ID=gentoo\n', None)}
for name, (txt, tool) in cases.items():
    f = Path(tempfile.mktemp()); f.write_text(txt); os.environ["OS_RELEASE_FILE"] = str(f)
    cmd = deps.install_command()
    ok(f"distro {name} → {tool or 'unknown'}", (tool in cmd) if tool else cmd is None, cmd)
    f.unlink()
os.environ.pop("OS_RELEASE_FILE")

# --- detect problems (PATH without tools)
ok("on this system: nothing missing", deps.problems() == [], deps.problems())
old = os.environ["PATH"]; os.environ["PATH"] = "/nonexistent"
probs = deps.problems(); os.environ["PATH"] = old
ok("without tools: all 6 reported missing", len([p for p in probs if "missing" in p]) == 6, probs)
ok("notice text contains the install and service command",
   deps.install_command() in deps.help_text(probs) and deps.SERVICES in deps.help_text(probs))

# --- dialog at start
m.CONFIG = OUT / "deps_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([])
deps.problems = lambda: ['Program "pactl" is missing']     # simulated
w = m.MainWindow(check_system=True); w.show()
e = time.time() + 1.5
while time.time() < e: app.processEvents(); time.sleep(0.02)
box = getattr(w, "_deps_box", None)
ok("notice dialog appears", box is not None and box.isVisible() and "pactl" in box.text())
btn = [b for b in box.buttons() if b.text() == "Copy command"] if box else []
if btn: btn[0].click(); app.processEvents()
ok("\"Copy command\" puts the command on the clipboard",
   btn and QApplication.clipboard().text().startswith(deps.install_command()), QApplication.clipboard().text()[:60])
box and box.close(); w.close(); m.CONFIG.unlink(missing_ok=True)

# --- bundled plugins
for k in ("denoise", "compressor", "duck"):
    ok(f"{k}: plugin found in plugins/", str(fxlib.BUNDLED_PLUGINS) in (fxlib.find_plugin(fxlib.TYPES[k]["plugin"]) or ""))

# --- libatomic fallback: simulate a system "without" libatomic
orig_find = ctypes.util.find_library
ctypes.util.find_library = lambda n: None if n == "atomic" else orig_find(n)
env = fxlib._spawn_env()
ok("fallback: plugin folder in LD_LIBRARY_PATH", str(fxlib.BUNDLED_PLUGINS) in env.get("LD_LIBRARY_PATH", ""))
ldd = subprocess.run(["ldd", str(fxlib.BUNDLED_PLUGINS / "librnnoise_ladspa.so")], env=env, capture_output=True, text=True).stdout
ok("…RNNoise then loads the bundled libatomic", f"{fxlib.BUNDLED_PLUGINS}/libatomic.so.1" in ldd,
   [l.strip() for l in ldd.splitlines() if "atomic" in l])
FID = "selftestdep"
fxlib.spawn({"id": FID, "type": "denoise", "params": fxlib.defaults("denoise")})
ctypes.util.find_library = orig_find
names = lambda: {n.name for n in pw.read_graph().nodes.values()}
e = time.time() + 8
while time.time() < e and f"diy_fx_{FID}_in" not in names(): time.sleep(0.2)
ok("…and noise suppression really starts with it", f"diy_fx_{FID}_in" in names())
fxlib.kill(FID); fxlib.delete_files(FID)

# --- migration from the old name: old desktop entries are replaced
tmpx = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"], os.environ["XDG_DATA_HOME"] = str(tmpx / "c"), str(tmpx / "d")
(tmpx / "c/autostart").mkdir(parents=True); (tmpx / "d/applications").mkdir(parents=True)
(tmpx / "c/autostart/diy-audio-router.desktop").write_text("[Desktop Entry]\nName=DIY Audio Router\n")
(tmpx / "d/applications/diy-audio-router.desktop").write_text("[Desktop Entry]\nName=DIY Audio Router\n")
m.migrate_legacy_entries()
na, nm = tmpx / "c/autostart/node-router.desktop", tmpx / "d/applications/node-router.desktop"
ok("old entries removed", not (tmpx / "c/autostart/diy-audio-router.desktop").exists()
   and not (tmpx / "d/applications/diy-audio-router.desktop").exists())
ok("autostart stays on (new entry, minimized)", na.exists() and "--minimized" in na.read_text() and "Name=Node-Router" in na.read_text())
ok("new app menu entry", nm.exists() and "--minimized" not in nm.read_text())
subprocess.run(["rm", "-rf", str(tmpx)])
finish(fails)
