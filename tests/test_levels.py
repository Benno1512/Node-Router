# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Level meters: test tone (not connected to any speaker), silent stream, test mic.
Meters follow the signal, stop when hidden/disabled, recorders never show as cards.
Temp config, test objects only, silent."""
import subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NR, OUT, SKIP, finish, wav_file  # noqa: E402  (also sets sys.path)
sys.path.insert(0, str(NR))
from PySide6.QtWidgets import QApplication  # noqa: E402
import main as m, pw_backend as pw, levels  # noqa: E402

MIC, TONE, SIL = "diy_selftest_lvl", "diy_selftest_lvltone", "diy_selftest_lvlsilent"
m.CONFIG = OUT / "levels_config.json"; m.CONFIG.unlink(missing_ok=True)
app = QApplication([]); fails = 0
def ok(n, c, i=""):
    global fails; fails += not c; print(("OK   " if c else "FAIL ") + n, i, flush=True)
def wait(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.02)
def until(cond, ms):
    e = time.time() + ms / 1000
    while time.time() < e:
        app.processEvents()
        if cond(): return True
        time.sleep(0.02)
    return cond()
def item(pred):
    return next((i for i in w.view.node_items.values() if pred(i.node)), None)
def recorders():
    return [n for n in pw.read_graph().nodes.values() if n.name.startswith(levels.PREFIX)]
def rec_procs():
    out = subprocess.run(["pgrep", "-af", "pw-record"], capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if levels.PREFIX in l]

pw.create_virtual_mic("Selftest Level", MIC)
tone = subprocess.Popen(["pw-play", "--target", "0", "-P",
                         f'{{ node.name = "{TONE}", node.autoconnect = false, application.name = "{TONE}" }}',
                         str(wav_file("sine30.wav"))])                  # amplitude 0.3, silent (unlinked)
sil = subprocess.Popen(["pacat", "--playback", "--raw", "--format=s16le", "--rate=48000", "--channels=2",
                        f"--client-name={SIL}", "/dev/zero"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)
try:
    w = m.MainWindow(); w.show(); w.resize(1100, 760)
    t = s = mic = None
    until(lambda: item(lambda n: n.app_name == TONE) and item(lambda n: n.app_name == SIL)
          and item(lambda n: n.name == MIC), 6000)
    t, s, mic = item(lambda n: n.app_name == TONE), item(lambda n: n.app_name == SIL), item(lambda n: n.name == MIC)
    expect = levels.to_meter(0.3)                                       # ≈ 0.83 (-10.5 dBFS)
    ok("tone card: meter shows the test tone (~-10.5 dBFS)",
       until(lambda: abs(t.vol.meter - expect) < 0.04, 6000), (round(t.vol.meter, 3), round(expect, 3)))
    ok("silent stream: meter on, bar empty", until(lambda: s.vol.meter_on, 4000) and s.vol.meter == 0.0,
       (s.vol.meter_on, s.vol.meter))
    ok("test mic without input: bar empty", mic.vol.meter_on and mic.vol.meter == 0.0, (mic.vol.meter_on, mic.vol.meter))
    ok("no clip indicator", not t.vol.clip)
    ok("recorders never appear as cards",
       not [i for i in w.view.node_items.values() if i.node.name.startswith(levels.PREFIX)])
    # connect tone -> test mic: the mic's meter follows
    w.connect_nodes(t, mic)
    ok("tone -> test mic: mic meter follows", until(lambda: abs(mic.vol.meter - expect) < 0.05, 6000),
       round(mic.vol.meter, 3))
    # tone stops -> bar falls back to empty
    tone.terminate(); tone.wait()
    ok("tone gone: no stale level left", until(lambda: mic.vol.meter < 0.02, 4000), round(mic.vol.meter, 3))
    # hidden window (tray) -> meters stop, so microphones are not kept open
    n_on = len(w.meters.meters)
    w.hide(); wait(300)
    ok("window hidden: all recorders stopped", n_on > 0 and until(lambda: not recorders() and not rec_procs(), 4000),
       (n_on, [n.name for n in recorders()], rec_procs()))
    w.show(); wait(200)
    ok("window shown again: meters back", until(lambda: s.vol.meter_on if s.scene() else
                                                     item(lambda n: n.app_name == SIL).vol.meter_on, 5000))
    # disabled router -> meters off
    w.set_router_disabled(True)
    ok("router disabled: recorders stopped", until(lambda: not rec_procs(), 4000), rec_procs())
    w.set_router_disabled(False)
    ok("router enabled: meters back", until(lambda: rec_procs(), 5000))
    # crash leftovers are cleaned up at start
    w._quitting = True; w.close(); wait(300)
    ok("closing stops all recorders", until(lambda: not rec_procs(), 3000), rec_procs())
    stale = subprocess.Popen(["pw-record", "--target", "0", "-P", f'{{ node.name = "{levels.PREFIX}999999" }}',
                              str(OUT / "stale.wav")])
    time.sleep(0.8)
    ok("leftover recorder of a crashed instance is removed at start", stale.pid in levels.kill_stale())
    stale.wait(3)
finally:
    for p in (tone, sil):
        if p.poll() is None:
            p.terminate(); p.wait()
    pw.remove_virtual_mic(MIC)
finish(fails)
