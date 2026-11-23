# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Systemprüfung (deps.py), Hinweis-Dialog beim Start, mitgelieferte Plugins inkl.
libatomic-Rückfall für RNNoise (echter Effekt-Prozess, nur Test-IDs)."""
import ctypes.util, json, os, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, finish  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
import deps, fx as fxlib, main as m, pw_backend as pw  # noqa: E402

fails = 0
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)

# --- Distro-Erkennung
cases = {"ubuntu": ('ID=ubuntu\nID_LIKE=debian\n', "apt"), "mint": ('ID=linuxmint\nID_LIKE="ubuntu debian"\n', "apt"),
         "fedora": ('ID=fedora\n', "dnf"), "manjaro": ('ID=manjaro\nID_LIKE=arch\n', "pacman"),
         "tumbleweed": ('ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n', "zypper"), "gentoo": ('ID=gentoo\n', None)}
for name, (txt, tool) in cases.items():
    f = Path(tempfile.mktemp()); f.write_text(txt); os.environ["OS_RELEASE_FILE"] = str(f)
    cmd = deps.install_command()
    ok(f"Distro {name} → {tool or 'unbekannt'}", (tool in cmd) if tool else cmd is None, cmd)
    f.unlink()
os.environ.pop("OS_RELEASE_FILE")

# --- Probleme erkennen (PATH ohne Werkzeuge)
ok("auf diesem System: nichts fehlt", deps.problems() == [], deps.problems())
old = os.environ["PATH"]; os.environ["PATH"] = "/nonexistent"
probs = deps.problems(); os.environ["PATH"] = old
ok("ohne Werkzeuge: alle 6 als fehlend gemeldet", len([p for p in probs if "fehlt" in p]) == 6, probs)
ok("Hinweistext enthält Installations- und Dienstbefehl",
   deps.install_command() in deps.help_text(probs) and deps.SERVICES in deps.help_text(probs))

# --- Dialog beim Start
m.CONFIG = OUT / "deps_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([])
deps.problems = lambda: ["Programm „pactl“ fehlt"]          # simuliert
w = m.MainWindow(check_system=True); w.show()
e = time.time() + 1.5
while time.time() < e: app.processEvents(); time.sleep(0.02)
box = getattr(w, "_deps_box", None)
ok("Hinweis-Dialog erscheint", box is not None and box.isVisible() and "pactl" in box.text())
btn = [b for b in box.buttons() if b.text() == "Befehl kopieren"] if box else []
if btn: btn[0].click(); app.processEvents()
ok("„Befehl kopieren“ legt Befehl in die Zwischenablage",
   btn and QApplication.clipboard().text().startswith(deps.install_command()), QApplication.clipboard().text()[:60])
box and box.close(); w.close(); m.CONFIG.unlink(missing_ok=True)

# --- mitgelieferte Plugins
for k in ("denoise", "compressor", "duck"):
    ok(f"{k}: Plugin aus plugins/ gefunden", str(fxlib.BUNDLED_PLUGINS) in (fxlib.find_plugin(fxlib.TYPES[k]["plugin"]) or ""))

# --- libatomic-Rückfall: System „ohne“ libatomic simulieren
orig_find = ctypes.util.find_library
ctypes.util.find_library = lambda n: None if n == "atomic" else orig_find(n)
env = fxlib._spawn_env()
ok("Rückfall: Plugin-Ordner in LD_LIBRARY_PATH", str(fxlib.BUNDLED_PLUGINS) in env.get("LD_LIBRARY_PATH", ""))
ldd = subprocess.run(["ldd", str(fxlib.BUNDLED_PLUGINS / "librnnoise_ladspa.so")], env=env, capture_output=True, text=True).stdout
ok("…RNNoise lädt dann die mitgelieferte libatomic", f"{fxlib.BUNDLED_PLUGINS}/libatomic.so.1" in ldd,
   [l.strip() for l in ldd.splitlines() if "atomic" in l])
FID = "selftestdep"
fxlib.spawn({"id": FID, "type": "denoise", "params": fxlib.defaults("denoise")})
ctypes.util.find_library = orig_find
names = lambda: {n.name for n in pw.read_graph().nodes.values()}
e = time.time() + 8
while time.time() < e and f"diy_fx_{FID}_in" not in names(): time.sleep(0.2)
ok("…und die Rauschunterdrückung startet damit wirklich", f"diy_fx_{FID}_in" in names())
fxlib.kill(FID); fxlib.delete_files(FID)

# --- Übergang vom alten Namen: alte Desktop-Einträge werden ersetzt
tmpx = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"], os.environ["XDG_DATA_HOME"] = str(tmpx / "c"), str(tmpx / "d")
(tmpx / "c/autostart").mkdir(parents=True); (tmpx / "d/applications").mkdir(parents=True)
(tmpx / "c/autostart/diy-audio-router.desktop").write_text("[Desktop Entry]\nName=DIY Audio Router\n")
(tmpx / "d/applications/diy-audio-router.desktop").write_text("[Desktop Entry]\nName=DIY Audio Router\n")
m.migrate_legacy_entries()
na, nm = tmpx / "c/autostart/node-router.desktop", tmpx / "d/applications/node-router.desktop"
ok("alte Einträge entfernt", not (tmpx / "c/autostart/diy-audio-router.desktop").exists()
   and not (tmpx / "d/applications/diy-audio-router.desktop").exists())
ok("Autostart bleibt an (neuer Eintrag, minimiert)", na.exists() and "--minimized" in na.read_text() and "Name=Node-Router" in na.read_text())
ok("neuer Startmenü-Eintrag", nm.exists() and "--minimized" not in nm.read_text())
subprocess.run(["rm", "-rf", str(tmpx)])
finish(fails)
