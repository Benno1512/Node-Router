# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""Level meters for the cards.

Each metered node gets its own small recorder: `pw-record` writing raw 32-bit float
samples (2 channels, 8 kHz) to stdout, created with node.autoconnect=false and
linked by us to the node's output ports (for output devices: their monitor
ports). The peak of every chunk is shown as a bar in dBFS (-60 … 0 dB).

Meters only run while the window is visible: a meter on a microphone keeps that
microphone open, so it must not run permanently in the background.
"""
from __future__ import annotations

import array
import math
import subprocess
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QProcess, QTimer

import pw_backend as pw

PREFIX = "diy_meter_"
RATE = 8000                  # enough for a level display, little data to read
FLOOR_DB = -60.0
RELEASE_PER_S = 1.5          # falling speed of the bar (full scale per second)
STALE_S = 0.35               # no data for this long -> the node is silent/inactive
CLIP = 0.989                 # ≈ -0.1 dBFS
CLIP_HOLD_S = 1.0


def to_meter(peak: float) -> float:
    """Linear peak -> 0..1 on a dB scale."""
    if peak <= 1e-6:
        return 0.0
    db = 20 * math.log10(peak)
    return min(max((db - FLOOR_DB) / -FLOOR_DB, 0.0), 1.0)


def source_ports(node: pw.Node) -> list[pw.Port]:
    """The ports whose signal the card stands for: normal outputs, or the
    monitor ports of an output device."""
    return node.playable_out or [p for p in node.out_ports if p.monitor]


def link_pairs(node: pw.Node, rec: pw.Node) -> list[tuple[int, int]]:
    outs, ins = source_ports(node), rec.in_ports
    if not outs or not ins:
        return []
    by_ch = {p.channel: p for p in ins}
    left, right = by_ch.get("FL", ins[0]), by_ch.get("FR", ins[-1])
    if len(outs) == 1:
        return [(outs[0].id, left.id)]
    named = {p.channel: p for p in outs}
    a, b = named.get("FL", outs[0]), named.get("FR", outs[1])
    return [(a.id, left.id), (b.id, right.id)]


def kill_stale() -> list[int]:
    """Recorders left over from a crashed instance (ours only: pw-record with
    a diy_meter_ node name)."""
    killed = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if cmd and cmd[0].endswith(b"pw-record") and any(PREFIX.encode() in a for a in cmd):
            subprocess.run(["kill", p.name], capture_output=True)
            killed.append(int(p.name))
    return killed


class Meter:
    def __init__(self, node_id: int, parent: QObject):
        self.node_id = node_id
        self.name = f"{PREFIX}{node_id}"
        self.level = 0.0                 # displayed value 0..1
        self.target = 0.0                # value of the latest chunk
        self.clip_until = 0.0
        self.last_data = 0.0
        self.last_link_try = 0.0
        self.started = time.monotonic()
        self.shown_clip = False
        self._rest = b""
        self.proc = QProcess(parent)
        self.proc.setProcessChannelMode(QProcess.SeparateChannels)
        self.proc.setStandardErrorFile(QProcess.nullDevice())
        self.proc.readyReadStandardOutput.connect(self._read)
        props = (f'{{ node.name = "{self.name}", node.description = "Node-Router level meter", '
                 f'media.name = "Node-Router level meter", application.name = "Node-Router", '
                 f'node.autoconnect = false, node.dont-reconnect = true }}')
        self.proc.start("pw-record", ["--target", "0", "--rate", str(RATE), "--channels", "2",
                                      "--format", "f32", "--latency", "40ms", "-P", props, "-"])

    def _read(self):
        data = self._rest + bytes(self.proc.readAllStandardOutput())
        cut = len(data) - len(data) % 4
        self._rest = data[cut:]
        if not cut:
            return
        a = array.array("f")
        a.frombytes(data[:cut])
        peak = max(max(a), -min(a))
        self.target = to_meter(peak)
        self.last_data = time.monotonic()
        if peak >= CLIP:
            self.clip_until = self.last_data + CLIP_HOLD_S

    def tick(self, dt: float, now: float) -> bool:
        """Advance the display value; True if it changed visibly."""
        target = self.target if now - self.last_data < STALE_S else 0.0
        old = self.level
        if target >= self.level:
            self.level = target                          # instant attack
        else:
            self.level = max(target, self.level - RELEASE_PER_S * dt)
        return abs(self.level - old) > 0.002

    @property
    def clipping(self) -> bool:
        return time.monotonic() < self.clip_until

    def stop(self):
        self.proc.readyReadStandardOutput.disconnect(self._read)
        self.proc.kill()
        self.proc.waitForFinished(500)
        self.proc.deleteLater()


class LevelMeters(QObject):
    """Keeps one recorder per wanted node and reports levels via on_level."""

    def __init__(self, on_level: Callable[[int, float, bool], None], parent: QObject | None = None):
        super().__init__(parent)
        self.on_level = on_level
        self.enabled = False
        self.meters: dict[int, Meter] = {}
        self._last = time.monotonic()
        self.timer = QTimer(self, interval=33, timeout=self._tick)

    def sync(self, graph: pw.Graph, wanted: list[pw.Node]) -> None:
        """Start/stop recorders for the wanted nodes and link new ones."""
        want = {n.id: n for n in wanted if source_ports(n)} if self.enabled else {}
        for nid in list(self.meters):
            m = self.meters[nid]
            dead = m.proc.state() == QProcess.NotRunning and time.monotonic() - m.started > 2
            if nid not in want or dead:
                self.meters.pop(nid).stop()          # node gone, or the recorder died
                self.on_level(nid, 0.0, False)
        for nid in want:
            if nid not in self.meters:
                self.meters[nid] = Meter(nid, self)
                self.on_level(nid, 0.0, False)        # show the (empty) bar right away
        if self.meters and not self.timer.isActive():
            self._last = time.monotonic(); self.timer.start()
        elif not self.meters:
            self.timer.stop()
        recs = {n.name: n for n in graph.nodes.values() if n.name.startswith(PREFIX)}
        linked = {(l.out_node, l.in_node) for l in graph.links}
        now = time.monotonic()
        for nid, m in self.meters.items():
            rec = recs.get(m.name)
            if rec is None or (nid, rec.id) in linked or now - m.last_link_try < 1.0:
                continue
            m.last_link_try = now
            for op, ip in link_pairs(want[nid], rec):
                subprocess.run(["pw-link", str(op), str(ip)], capture_output=True)

    def stop_all(self) -> None:
        for nid in list(self.meters):
            self.meters.pop(nid).stop()
            self.on_level(nid, 0.0, False)
        self.timer.stop()

    def _tick(self):
        now = time.monotonic()
        dt, self._last = now - self._last, now
        for nid, m in self.meters.items():
            changed, clip = m.tick(dt, now), m.clipping
            if changed or clip != m.shown_clip:
                m.shown_clip = clip
                self.on_level(nid, m.level, clip)
