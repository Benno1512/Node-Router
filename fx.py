# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Effect blocks as PipeWire filter-chain.

Every block runs as its own `pipewire -c <conf>` process (detached from the
router, so it keeps running when the router quits – like links/virtual mics).
It creates two nodes:
    diy_fx_<id>_in   (Stream/Input/Audio, ports input_FL/FR)
    diy_fx_<id>_out  (Stream/Output/Audio, ports output_FL/FR)
both with node.autoconnect = false, so WirePlumber does not connect anything.

Sliders are changed live via `pw-cli set-param <in-node> Props { params = [...] }`.
Only the reverb decay changes the impulse response -> restart.
Tested with PipeWire 1.0.5 (builtin bq_highpass/bq_*shelf/bq_peaking, delay,
convolver with WAV via libsndfile, copy, mixer).
"""
from __future__ import annotations

import ctypes.util
import math
import os
import random
import signal
import struct
import subprocess
import time
import uuid
import wave
from pathlib import Path

from paths import BUNDLED_PLUGINS, FX_DIR, PLUGIN_DIR  # noqa: E402  (source: next to the program, bundled: ~/.local/share)
PREFIX = "diy_fx_"
LADSPA_DIRS = ["/usr/lib/ladspa", "/usr/lib/x86_64-linux-gnu/ladspa", "/usr/local/lib/ladspa",
               str(Path.home() / ".ladspa")]
LSP_URI = "http://lsp-plug.in/plugins/ladspa/"


def find_plugin(filename: str) -> str | None:
    for d in dict.fromkeys([str(PLUGIN_DIR), str(BUNDLED_PLUGINS)] + LADSPA_DIRS):
        p = Path(d) / filename
        if p.is_file():
            return str(p)
    return None


def db_to_gain(db: float) -> float:
    return 10 ** (db / 20.0)

# ------------------------------------------------------------------ types
# parameters: key, label, min, max, default, unit, log (logarithmic scale),
# restart (a change needs a restart instead of live control)
TYPES: dict[str, dict] = {
    "highpass": {
        "title": "High-pass",
        "hint": "Removes hum and rumble below the frequency",
        "params": [
            {"key": "freq", "label": "Frequency", "min": 20, "max": 1000,
             "default": 80, "unit": "Hz", "log": True},
        ],
    },
    "eq": {
        "title": "Equalizer",
        "hint": "Bass 120 Hz · Mids 1 kHz · Treble 6 kHz",
        "params": [
            {"key": "low", "label": "Bass", "min": -12, "max": 12, "default": 0, "unit": "dB"},
            {"key": "mid", "label": "Mids", "min": -12, "max": 12, "default": 0, "unit": "dB"},
            {"key": "high", "label": "Treble", "min": -12, "max": 12, "default": 0, "unit": "dB"},
        ],
    },
    "delay": {
        "title": "Delay",
        "hint": "Delays the signal (e.g. to sync audio with video)",
        "params": [
            {"key": "ms", "label": "Time", "min": 0, "max": 2000, "default": 250, "unit": "ms"},
        ],
    },
    "reverb": {
        "title": "Reverb",
        "hint": "Room reverb (convolution with a generated impulse response)",
        "params": [
            {"key": "mix", "label": "Mix", "min": 0, "max": 100, "default": 30, "unit": "%"},
            {"key": "decay", "label": "Decay", "min": 0.3, "max": 6.0, "default": 1.8,
             "unit": "s", "restart": True},
        ],
    },
    "denoise": {
        "title": "Noise suppression",
        "hint": "RNNoise: lets only speech through (fans, keyboard, noise are removed)",
        "plugin": "librnnoise_ladspa.so",
        "missing": "RNNoise plugin missing: plugins/librnnoise_ladspa.so "
                   "(github.com/werman/noise-suppression-for-voice)",
        "params": [
            {"key": "vad", "label": "Threshold", "min": 0, "max": 95, "default": 50, "unit": "%"},
            {"key": "grace", "label": "Hold", "min": 0, "max": 1000, "default": 200, "unit": "ms"},
        ],
    },
    "compressor": {
        "title": "Compressor",
        "hint": "Evens out loudness: level above the threshold is reduced by the ratio",
        "plugin": "lsp-plugins-ladspa.so",
        "missing": "LSP Plugins missing (plugins/lsp-plugins-ladspa.so or: sudo apt install lsp-plugins-ladspa)",
        "params": [
            {"key": "thresh", "label": "Threshold", "min": -60, "max": 0, "default": -20, "unit": "dB"},
            {"key": "ratio", "label": "Ratio", "min": 1, "max": 20, "default": 4, "unit": ":1"},
            {"key": "attack", "label": "Attack", "min": 1, "max": 200, "default": 10, "unit": "ms"},
            {"key": "release", "label": "Release", "min": 10, "max": 1000, "default": 100, "unit": "ms"},
            {"key": "makeup", "label": "Make-up", "min": 0, "max": 24, "default": 0, "unit": "dB"},
        ],
    },
    "duck": {
        "title": "Ducking",
        "hint": "Lowers \"Music\" as soon as \"Priority\" (e.g. a mic) exceeds the threshold. "
                "Output = lowered music; connect the priority itself directly as well.",
        "plugin": "lsp-plugins-ladspa.so",
        "missing": "LSP Plugins missing (plugins/lsp-plugins-ladspa.so or: sudo apt install lsp-plugins-ladspa)",
        # Two inputs. Positions RL/RR instead of AUX0/1: PipeWire 1.0.5 drops
        # AUX channels on the filter-chain input (measured on the system).
        "inputs": [
            {"group": "main", "label": "Music", "channels": ["FL", "FR"]},
            {"group": "prio", "label": "Priority", "channels": ["RL", "RR"]},
        ],
        "params": [
            {"key": "thresh", "label": "Threshold", "min": -60, "max": 0, "default": -35, "unit": "dB"},
            {"key": "ratio", "label": "Strength", "min": 1, "max": 20, "default": 8, "unit": ":1"},
            {"key": "release", "label": "Release", "min": 50, "max": 3000, "default": 500, "unit": "ms"},
        ],
    },
}


def input_groups(kind: str) -> list[dict]:
    """Inputs of a block; default: one input without a group."""
    return TYPES[kind].get("inputs") or [{"group": None, "label": "", "channels": None}]


def channels_for(kind: str, group: str | None) -> list[str] | None:
    for g in input_groups(kind):
        if g["group"] == group:
            return g["channels"]
    return None


def available(kind: str) -> tuple[bool, str]:
    plug = TYPES[kind].get("plugin")
    if plug and not find_plugin(plug):
        return False, TYPES[kind]["missing"]
    return True, ""


def defaults(kind: str) -> dict[str, float]:
    return {p["key"]: p["default"] for p in TYPES[kind]["params"]}


def new_id() -> str:
    return uuid.uuid4().hex[:6]


def node_names(fx_id: str) -> tuple[str, str]:
    return f"{PREFIX}{fx_id}_in", f"{PREFIX}{fx_id}_out"


def controls(kind: str, params: dict) -> list[tuple[str, float]]:
    """Parameter values -> filter-chain control values ("node:Port", value)."""
    if kind == "highpass":
        return [("hp:Freq", float(params["freq"]))]
    if kind == "eq":
        return [("low:Gain", float(params["low"])), ("mid:Gain", float(params["mid"])),
                ("high:Gain", float(params["high"]))]
    if kind == "delay":
        return [("dl:Delay (s)", float(params["ms"]) / 1000.0)]
    if kind == "reverb":
        wet = float(params["mix"]) / 100.0
        dry = 1.0 - 0.5 * wet            # keep some dry signal at 100 %, sounds more natural
        return [(f"mix{c}:Gain 1", dry) for c in "LR"] + [(f"mix{c}:Gain 2", wet) for c in "LR"]
    if kind == "denoise":
        return [("rn:VAD Threshold (%)", float(params["vad"])),
                ("rn:VAD Grace Period (ms)", float(params["grace"]))]
    if kind == "compressor":
        return [("comp:Attack threshold (G)", db_to_gain(params["thresh"])),
                ("comp:Ratio", float(params["ratio"])),
                ("comp:Attack time (ms)", float(params["attack"])),
                ("comp:Release time (ms)", float(params["release"])),
                ("comp:Makeup gain (G)", db_to_gain(params["makeup"]))]
    if kind == "duck":
        return [("sc:Attack threshold (G)", db_to_gain(params["thresh"])),
                ("sc:Ratio", float(params["ratio"])),
                ("sc:Release time (ms)", float(params["release"]))]
    return []


# ------------------------------------------------------------ config

def _ctrl(pairs: list[tuple[str, float]], node: str) -> str:
    items = [f'"{k.split(":", 1)[1]}" = {v:.6g}' for k, v in pairs if k.split(":", 1)[0] == node]
    return "{ " + " ".join(items) + " }"


def _graph(kind: str, fx_id: str, params: dict) -> str:
    c = controls(kind, params)
    if kind == "highpass":   # 1 input/output -> PipeWire duplicates per channel
        return f"""{{ nodes = [ {{ type = builtin name = hp label = bq_highpass
                       control = {{ "Freq" = {params['freq']:.6g} "Q" = 0.707 }} }} ] }}"""
    if kind == "eq":
        return f"""{{ nodes = [
            {{ type = builtin name = low  label = bq_lowshelf  control = {{ "Freq" = 120.0  "Q" = 0.7 "Gain" = {params['low']:.6g} }} }}
            {{ type = builtin name = mid  label = bq_peaking   control = {{ "Freq" = 1000.0 "Q" = 0.8 "Gain" = {params['mid']:.6g} }} }}
            {{ type = builtin name = high label = bq_highshelf control = {{ "Freq" = 6000.0 "Q" = 0.7 "Gain" = {params['high']:.6g} }} }}
          ]
          links = [ {{ output = "low:Out" input = "mid:In" }} {{ output = "mid:Out" input = "high:In" }} ] }}"""
    if kind == "delay":
        return f"""{{ nodes = [ {{ type = builtin name = dl label = delay
                       config = {{ "max-delay" = 2.1 }}
                       control = {{ "Delay (s)" = {float(params['ms']) / 1000:.6g} }} }} ] }}"""
    if kind == "denoise":    # mono plugin, PipeWire duplicates it per channel
        return (f'{{ nodes = [ {{ type = ladspa name = rn plugin = "{find_plugin(TYPES[kind]["plugin"])}" '
                f'label = noise_suppressor_mono control = {_ctrl(c, "rn")} }} ] }}')
    if kind in ("compressor", "duck"):
        lsp = find_plugin(TYPES[kind]["plugin"])
        name = "comp" if kind == "compressor" else "sc"
        label = LSP_URI + ("compressor_stereo" if kind == "compressor" else "sc_compressor_stereo")
        ctrl = _ctrl(c, name)[:-1]
        if kind == "duck":                       # 2 = external sidechain (measured)
            ctrl += '"Sidechain type" = 2 "Attack time (ms)" = 5 '
        ins = '"{0}:Input L" "{0}:Input R"'.format(name)
        if kind == "duck":
            ins += ' "sc:Sidechain input Left" "sc:Sidechain input Right"'
        return (f'{{ nodes = [ {{ type = ladspa name = {name} plugin = "{lsp}" label = "{label}" '
                f'control = {ctrl}}} }} ]\n inputs = [ {ins} ] '
                f'outputs = [ "{name}:Output L" "{name}:Output R" ] }}')
    if kind == "reverb":     # explicit L/R so the reverb sounds wide
        ir = ir_path(fx_id)
        nodes, links = [], []
        for ch, idx in (("L", 0), ("R", 1)):
            nodes += [
                f'{{ type = builtin name = split{ch} label = copy }}',
                f'{{ type = builtin name = conv{ch} label = convolver config = {{ filename = "{ir}" channel = {idx} }} }}',
                f'{{ type = builtin name = mix{ch} label = mixer control = {_ctrl(c, "mix" + ch)} }}',
            ]
            links += [
                f'{{ output = "split{ch}:Out" input = "mix{ch}:In 1" }}',
                f'{{ output = "split{ch}:Out" input = "conv{ch}:In" }}',
                f'{{ output = "conv{ch}:Out" input = "mix{ch}:In 2" }}',
            ]
        return ("{ nodes = [ " + "\n ".join(nodes) + " ]\n links = [ " + "\n ".join(links) +
                ' ]\n inputs = [ "splitL:In" "splitR:In" ] outputs = [ "mixL:Out" "mixR:Out" ] }')
    raise ValueError(kind)


def conf_path(fx_id: str) -> Path:
    return FX_DIR / f"{fx_id}.conf"


def pid_path(fx_id: str) -> Path:
    return FX_DIR / f"{fx_id}.pid"


def ir_path(fx_id: str) -> Path:
    return FX_DIR / f"{fx_id}_ir.wav"


def write_conf(fx: dict) -> Path:
    FX_DIR.mkdir(parents=True, exist_ok=True)
    fid, kind, params = fx["id"], fx["type"], fx["params"]
    if kind == "reverb":
        make_ir(ir_path(fid), float(params["decay"]))
    nin, nout = node_names(fid)
    title = TYPES[kind]["title"]
    chans = [ch for g in input_groups(kind) for ch in (g["channels"] or ["FL", "FR"])]
    cap_fmt = f"audio.channels = {len(chans)} audio.position = [ {' '.join(chans)} ]"
    text = f"""# generated by Node-Router – rewritten on every start
context.properties = {{ log.level = 0 }}
context.spa-libs = {{
    audio.convert.* = audioconvert/libspa-audioconvert
    support.*       = support/libspa-support
}}
context.modules = [
  {{ name = libpipewire-module-rt args = {{ }} flags = [ ifexists nofail ] }}
  {{ name = libpipewire-module-protocol-native }}
  {{ name = libpipewire-module-client-node }}
  {{ name = libpipewire-module-adapter }}
  {{ name = libpipewire-module-filter-chain
    args = {{
      node.description = "{title} (DIY {fid})"
      media.name       = "{title} (DIY {fid})"
      filter.graph = {_graph(kind, fid, params)}
      capture.props  = {{ node.name = "{nin}"  node.autoconnect = false {cap_fmt} }}
      playback.props = {{ node.name = "{nout}" node.autoconnect = false audio.channels = 2 audio.position = [ FL FR ] }}
    }}
  }}
]
"""
    p = conf_path(fid)
    p.write_text(text)
    return p


def make_ir(path: Path, decay: float, sr: int = 48000) -> None:
    """Stereo impulse response: decorrelated, exponentially decaying noise tail
    (-60 dB after `decay` s), slightly low-pass filtered, energy normalized."""
    n = max(1, int(sr * decay))
    pre = int(sr * 0.012)                      # 12 ms pre-delay
    rng = random.Random(1234)
    chans = []
    for _ in range(2):
        lp, out = 0.0, []
        for i in range(n):
            t = i / sr
            x = rng.uniform(-1, 1) * math.exp(-6.9 * t / decay)
            k = 0.35 + 0.5 * min(1.0, t / decay)   # gets darker over time
            lp += (x - lp) * (1 - k)
            out.append(lp)
        energy = math.sqrt(sum(v * v for v in out)) or 1.0
        chans.append([0.0] * pre + [v / energy * 0.9 for v in out])
    peak = max(abs(v) for ch in chans for v in ch) or 1.0
    scale = min(1.0, 0.99 / peak)
    frames = b"".join(struct.pack("<hh", int(chans[0][i] * scale * 32767), int(chans[1][i] * scale * 32767))
                      for i in range(len(chans[0])))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(frames)
    # note: energy normalization -> wet level ~ dry level


# --------------------------------------------------------------- processes

def running_pid(fx_id: str) -> int | None:
    """PID of our process for this block – only if its command line really
    contains our config (never touch other pipewire processes)."""
    try:
        pid = int(pid_path(fx_id).read_text().strip())
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except (OSError, ValueError):
        return None
    return pid if str(conf_path(fx_id)).encode() in cmd else None


def _spawn_env() -> dict:
    """RNNoise needs libatomic.so.1, which is missing on some systems. Only then
    make the bundled copy (plugins/libatomic.so.1) visible to the effect
    process – existing system libraries take precedence."""
    env = dict(os.environ)
    if ctypes.util.find_library("atomic") is None:
        dirs = [str(d) for d in (PLUGIN_DIR, BUNDLED_PLUGINS) if (d / "libatomic.so.1").is_file()]
        if dirs:
            env["LD_LIBRARY_PATH"] = ":".join(dirs + [p for p in [env.get("LD_LIBRARY_PATH")] if p])
    return env


def spawn(fx: dict) -> None:
    conf = write_conf(fx)
    p = subprocess.Popen(["pipewire", "-c", str(conf)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=_spawn_env(),
                         start_new_session=True)   # survives quitting the router
    pid_path(fx["id"]).write_text(str(p.pid))


def kill(fx_id: str, timeout: float = 1.5) -> None:
    pid = running_pid(fx_id)
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pid = None
        end = time.time() + timeout
        while pid and time.time() < end:
            try:
                os.waitpid(pid, os.WNOHANG)   # our own child -> avoid a zombie
            except ChildProcessError:
                pass
            if not Path(f"/proc/{pid}").exists() or b"Z" in _state(pid):
                break
            time.sleep(0.05)
    pid_path(fx_id).unlink(missing_ok=True)


def _state(pid: int) -> bytes:
    try:
        return Path(f"/proc/{pid}/stat").read_bytes().split(b")")[-1].split()[0]
    except (OSError, IndexError):
        return b"X"


def delete_files(fx_id: str) -> None:
    for p in (conf_path(fx_id), pid_path(fx_id), ir_path(fx_id)):
        p.unlink(missing_ok=True)


def set_controls(in_node_id: int, pairs: list[tuple[str, float]]) -> None:
    if not pairs:
        return
    body = " ".join(f'"{k}" {v:.6g}' for k, v in pairs)
    subprocess.run(["pw-cli", "set-param", str(in_node_id), "Props", f"{{ params = [ {body} ] }}"],
                   capture_output=True, text=True)
