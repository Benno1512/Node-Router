# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""Shared helpers for the tests.

The tests open real windows and create real PipeWire objects
(virtual test mics `diy_selftest_*`, silent test streams, effect processes).
They use their own config in a temp folder – never the user's config.json –
and play nothing through the speakers (test streams with node.autoconnect=false
or silence from /dev/zero).
"""
from __future__ import annotations

import math
import os
import random
import struct
import sys
import tempfile
import wave
from pathlib import Path

NR = Path(__file__).resolve().parent.parent              # repository root
OUT = Path(os.environ.get("DIY_TEST_OUT", Path(tempfile.gettempdir()) / "diy_router_tests"))
OUT.mkdir(parents=True, exist_ok=True)
if str(NR) not in sys.path:
    sys.path.insert(0, str(NR))

SKIP = 77                                                # exit code "skipped"


def wav_file(name: str) -> Path:
    """Generate the test signals (48 kHz, stereo) once in the temp folder."""
    f = OUT / name
    if f.exists():
        return f
    rng = random.Random(7)
    gens = {
        "sine30.wav": (30, lambda i: int(0.3 * 32767 * math.sin(2 * math.pi * 440 * i / 48000))),
        "tone40.wav": (40, lambda i: int(0.5 * 32767 * math.sin(2 * math.pi * 440 * i / 48000))),
        "noise40.wav": (40, lambda i: int(rng.uniform(-1, 1) * 6000)),
    }
    secs, gen = gens[name]
    w = wave.open(str(f), "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
    w.writeframes(b"".join(struct.pack("<hh", v, v) for v in (gen(i) for i in range(48000 * secs))))
    w.close()
    return f


def finish(fails: int) -> None:
    print("FAILS:", fails, flush=True)
    sys.exit(1 if fails else 0)
