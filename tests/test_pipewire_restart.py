# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""ECHTER Neustart von PipeWire (pipewire, pipewire-pulse, wireplumber).

Nicht Teil von run_all.py: unterbricht den Ton aller Programme kurz, und virtuelle
Mikros/Effekte, die gerade kein laufender Router pflegt, verschwinden bis zum
nächsten Router-Start. Nur manuell ausführen:

    ../.venv/bin/python tests/test_pipewire_restart.py --ja-wirklich
"""
import json, math, struct, subprocess, sys, time, wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, finish, wav_file  # noqa: E402
from PySide6.QtCore import QPointF, QProcess  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
import main as m, pw_backend as pw, fx as fxlib  # noqa: E402

if "--ja-wirklich" not in sys.argv:
    print(__doc__); sys.exit(2)

MIC, TONE = "diy_selftest_pwr", "diy_selftest_tone"
m.CONFIG = OUT / "pwrestart_config.json"
m.CONFIG.write_text(json.dumps({"virtual_mics": [{"name": MIC, "label": "Selftest PW Restart"}]}))
app = QApplication([]); fails = 0
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
def until(cond, ms):
    t0 = time.time(); e = t0 + ms / 1000
    while time.time() < e:
        app.processEvents()
        try:
            if cond(): return time.time() - t0
        except Exception:
            pass
        time.sleep(0.1)
    return None
def graph():
    return pw.read_graph()
def linked(src_pred, dst_pred):
    g = graph()
    return any(g.nodes.get(l.out_node) and g.nodes.get(l.in_node) and src_pred(g.nodes[l.out_node])
               and dst_pred(g.nodes[l.in_node]) for l in g.links)
def tone():
    return subprocess.Popen(["pw-play", "-P", f"{{ node.autoconnect = false node.name = {TONE} application.name = {TONE} }}",
                             str(wav_file("tone40.wav"))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

is_tone = lambda n: n.app_name == TONE
is_fx_in, is_fx_out = (lambda n: n.is_fx_in), (lambda n: n.is_fx_out)
is_mic = lambda n: n.name == MIC

# Aufbau: Testton -> Hochpass -> Test-Mikro
p = tone(); time.sleep(1)
w = m.MainWindow(); w.show(); wait(2500); v = w.view
w.add_effect("highpass", QPointF(v.grid_span()[0] + 150, 120))
ok("Aufbau: Mikro + Hochpass laufen", until(lambda: any(i.running for i in v.fx_items.values())
                                          and any(n.name == MIC for n in graph().nodes.values()), 8000) is not None)
hp = next(iter(v.fx_items.values()))
item = lambda pred: next(i for i in v.node_items.values() if pred(i.node))
w.connect_nodes(item(is_tone), hp); wait(600); w.connect_nodes(hp, item(is_mic)); wait(1000)
r0 = rms(); ok("Ton kommt vor dem Neustart an", r0 > 2000, f"RMS {r0:.0f}")
pid0 = fxlib.running_pid(hp.fx["id"])

# ECHTER Neustart
print("…starte pipewire, pipewire-pulse, wireplumber neu", flush=True)
t_restart = time.time()
r = subprocess.run(["systemctl", "--user", "restart", "pipewire.service", "pipewire-pulse.service", "wireplumber.service"],
                   capture_output=True, text=True)
ok("systemctl restart", r.returncode == 0, r.stderr.strip())
p.kill()

t = until(lambda: w.mon.state() == QProcess.Running and w.graph.nodes and
          any(n.name == MIC for n in graph().nodes.values()), 20000)
ok("virtuelles Mikro wieder da", t is not None, f"nach {t:.1f} s" if t else "")
t = until(lambda: any(i.running for i in v.fx_items.values()) and fxlib.running_pid(hp.fx["id"]) not in (None, pid0), 25000)
ok("Effekt neu gestartet (neuer Prozess)", t is not None, f"nach {t:.1f} s" if t else f"pid {fxlib.running_pid(hp.fx['id'])} (vorher {pid0})")
ok("Überwachung läuft wieder", w.mon.state() == QProcess.Running)
t = until(lambda: linked(is_fx_out, is_mic), 10000)
ok("Route Hochpass → Mikro wiederhergestellt", t is not None, f"nach {t:.1f} s" if t else "")
p = tone()
t = until(lambda: linked(is_tone, is_fx_in), 8000)
ok("Testton (neu gestartet) wieder an den Hochpass", t is not None, f"nach {t:.1f} s" if t else "")
wait(800)
r1 = rms(); ok("Ton kommt nach dem Neustart wieder an", r1 > 2000, f"RMS {r1:.0f}")
print(f"   gesamt seit Neustart: {time.time() - t_restart:.1f} s", flush=True)
w.grab().save(str(OUT / "after_pw_restart.png"))

for it in list(v.fx_items.values()): w.remove_effect(it)
until(lambda: fxlib.running_pid(hp.fx["id"]) is None, 5000)
w.close(); p.kill(); pw.remove_virtual_mic(MIC); m.CONFIG.unlink(missing_ok=True)
finish(fails)
