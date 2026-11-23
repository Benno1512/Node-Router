# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""Starts the built AppImage like a user would (with a test config in temp folders) and
checks that it works with PipeWire from the single file: virtual mic
(pactl), effect process (pipewire -c), storage locations, icon, single instance.

    ./build_appimage.sh && .venv/bin/python tests/test_appimage.py
"""
import glob, json, os, signal, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish  # noqa: E402
import pw_backend as pw  # noqa: E402

imgs = sorted(glob.glob(str(NR / "build" / "Node-Router-*-x86_64.AppImage")))
if not imgs:
    print("SKIP: no AppImage built (./build_appimage.sh)"); sys.exit(SKIP)
IMG = imgs[-1]
fails = 0
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def until(cond, s):
    e = time.time() + s
    while time.time() < e:
        if cond(): return True
        time.sleep(0.2)
    return cond()

H = OUT / "appimage_home"
subprocess.run(["rm", "-rf", str(H)])
cfg_dir, data_dir = H / "config" / "node-router", H / "data" / "node-router"
cfg_dir.mkdir(parents=True)
MIC, FXID = "diy_selftest_appimg", "selftestai"
(cfg_dir / "config.json").write_text(json.dumps({
    "virtual_mics": [{"name": MIC, "label": "Selftest AppImage"}],
    "effects": [{"id": FXID, "type": "highpass", "params": {"freq": 80}, "x": 0.5, "y": 100},
                {"id": FXID + "dn", "type": "denoise", "params": {"vad": 50, "grace": 200}, "x": 0.2, "y": 200},
                {"id": FXID + "cp", "type": "compressor", "params": {"thresh": -20, "ratio": 4, "attack": 10,
                                                                     "release": 100, "makeup": 0}, "x": 0.8, "y": 200},
                {"id": FXID + "dk", "type": "duck", "params": {"thresh": -35, "ratio": 8, "release": 500},
                 "x": 0.5, "y": 350}]}))
env = dict(os.environ, XDG_CONFIG_HOME=str(H / "config"), XDG_DATA_HOME=str(H / "data"))
env.pop("DIY_ROUTER_CONFIG", None)

v = subprocess.run([IMG, "--version"], capture_output=True, text=True, env=env, timeout=60)
ok("--version", v.returncode == 0 and "Node-Router" in v.stdout, v.stdout.strip() or v.stderr.strip()[-200:])

t0 = time.time()
p = subprocess.Popen([IMG, "--minimized"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
names = lambda: {n.name for n in pw.read_graph().nodes.values()}
ok("virtual mic from the config created (pactl from the bundle)", until(lambda: MIC in names(), 25),
   f"after {time.time() - t0:.1f} s")
ok("effect process running (pipewire -c from the bundle)",
   until(lambda: {f"diy_fx_{FXID}_in", f"diy_fx_{FXID}_out"} <= names(), 25))
ok("effect files under ~/.local/share/node-router/fx", (data_dir / "fx" / f"{FXID}.conf").exists())
for suf, name in (("dn", "Noise suppression"), ("cp", "Compressor"), ("dk", "Ducking")):
    ok(f"{name} runs with the bundled plugin", until(lambda s=suf: f"diy_fx_{FXID}{s}_in" in names(), 15))
conf = (data_dir / "fx" / f"{FXID}dn.conf").read_text() if (data_dir / "fx" / f"{FXID}dn.conf").exists() else ""
ok("…plugin stored permanently under ~/.local/share (not in the AppImage mount)",
   f"{data_dir}/plugins/librnnoise_ladspa.so" in conf and ".mount_" not in conf, [l.strip() for l in conf.splitlines() if "plugin =" in l][:1])
ok("icon copied permanently to ~/.local/share", (data_dir / "icon.svg").exists())
ok("config read from ~/.config/node-router", (cfg_dir / "config.json").exists())
s = subprocess.run([IMG], env=env, capture_output=True, text=True, timeout=60)
ok("second start: already running", s.returncode == 0 and "already running" in s.stderr, s.stderr.strip()[-120:])
ok("AppImage keeps running", p.poll() is None)

p.send_signal(signal.SIGTERM)
try: out = p.communicate(timeout=10)[0]
except subprocess.TimeoutExpired: p.kill(); out = p.communicate()[0]
bad = [l for l in out.splitlines() if "Traceback" in l or "Error" in l or "error while loading" in l]
ok("no errors in the output", not bad, bad[:3])
time.sleep(3)                                   # the AppImage is unmounted now
alive = [s for s in ("", "dn", "cp", "dk") if f"diy_fx_{FXID}{s}_in" in names()]
ok("effects keep running after the AppImage quits", len(alive) == 4, alive)

# clean up: effect process (keeps running on purpose) + test mic
for pid_f in (data_dir / "fx").glob("*.pid"):
    try: os.kill(int(pid_f.read_text()), signal.SIGTERM)
    except (ProcessLookupError, ValueError): pass
pw.remove_virtual_mic(MIC)
until(lambda: not ({MIC, f"diy_fx_{FXID}_in"} & names()), 5)
subprocess.run(["rm", "-rf", str(H)])
finish(fails)
