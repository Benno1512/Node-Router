"""Gemeinsame Hilfen für die Tests.

Die Tests öffnen echte Fenster und legen echte PipeWire-Objekte an
(virtuelle Test-Mikros `diy_selftest_*`, stumme Test-Streams, Effekt-Prozesse).
Sie benutzen eine eigene Config im Temp-Ordner – nie die config.json des Nutzers –
und spielen nichts über Lautsprecher ab (Test-Streams mit node.autoconnect=false
bzw. Stille aus /dev/zero).
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

NR = Path(__file__).resolve().parent.parent              # node_router/
OUT = Path(os.environ.get("DIY_TEST_OUT", Path(tempfile.gettempdir()) / "diy_router_tests"))
OUT.mkdir(parents=True, exist_ok=True)
if str(NR) not in sys.path:
    sys.path.insert(0, str(NR))

SKIP = 77                                                # Exit-Code „übersprungen“


def wav_file(name: str) -> Path:
    """Testsignale (48 kHz, Stereo) einmalig im Temp-Ordner erzeugen."""
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
