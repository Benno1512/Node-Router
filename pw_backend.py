# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Benno1512 – Node-Router
"""PipeWire graph access via pw-dump / pw-link / pactl."""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field

VIRTUAL_PREFIX = "diy_"
FX_PREFIX = "diy_fx_"          # effect blocks (see fx.py)


@dataclass
class Port:
    id: int
    node_id: int
    direction: str          # "input" | "output"
    name: str
    channel: str            # FL, FR, MONO, ...
    monitor: bool


@dataclass
class Node:
    id: int
    name: str               # node.name
    description: str
    media_class: str
    app_name: str
    media_name: str
    volume: float | None = None   # like wpctl/pavucontrol: 1.0 = 100 % (cubic scale)
    mute: bool | None = None
    in_ports: list[Port] = field(default_factory=list)
    out_ports: list[Port] = field(default_factory=list)

    @property
    def is_virtual_mic(self) -> bool:
        return self.name.startswith(VIRTUAL_PREFIX) and "Source" in self.media_class

    @property
    def is_effect(self) -> bool:
        return self.name.startswith(FX_PREFIX)

    @property
    def is_fx_in(self) -> bool:
        return self.is_effect and self.name.endswith("_in")

    @property
    def is_fx_out(self) -> bool:
        return self.is_effect and self.name.endswith("_out")

    @property
    def is_stream(self) -> bool:
        return self.media_class.startswith("Stream/")

    @property
    def key(self) -> str:
        """Stable identity across restarts (pw ids change)."""
        if self.is_effect:
            return f"fx:{self.name}"
        if self.is_stream:
            return f"app:{self.app_name or self.name}"
        return f"dev:{self.name}"

    @property
    def label(self) -> str:
        if self.is_stream:
            return self.app_name or self.description or self.name
        return self.description or self.name

    @property
    def sublabel(self) -> str:
        if self.is_virtual_mic:
            return "Virtual microphone"
        if self.is_stream:
            return self.media_name or "Application"
        return {
            "Audio/Source": "Input device",
            "Audio/Sink": "Output device",
            "Audio/Source/Virtual": "Virtual source",
        }.get(self.media_class, self.media_class)

    # role in the router UI
    @property
    def is_left(self) -> bool:
        if self.is_virtual_mic or self.is_effect:
            return False
        if self.media_class in ("Audio/Source", "Audio/Source/Virtual",
                                "Stream/Output/Audio"):
            return bool(self.playable_out)
        return False

    @property
    def is_right(self) -> bool:
        if self.is_effect:
            return False
        if self.is_virtual_mic or self.media_class == "Audio/Sink":
            return bool(self.in_ports)
        return False

    @property
    def playable_out(self) -> list[Port]:
        return [p for p in self.out_ports if not p.monitor]


@dataclass
class Link:
    id: int
    out_node: int
    out_port: int
    in_node: int
    in_port: int


@dataclass
class Graph:
    nodes: dict[int, Node]
    links: list[Link]
    ports: dict[int, Port] = field(default_factory=dict)

    def in_channel(self, link: "Link") -> str:
        p = self.ports.get(link.in_port)
        return p.channel if p else ""

    def signature(self) -> tuple:
        return (
            tuple(sorted((n.id, n.label, len(n.in_ports), len(n.out_ports),
                          None if n.volume is None else round(n.volume, 3), n.mute)
                         for n in self.nodes.values())),
            tuple(sorted((l.out_port, l.in_port) for l in self.links)),
        )


def _dump_objects(raw: str) -> list[dict]:
    """pw-dump output -> list of objects.

    If the graph changes during the dump (client comes/goes, app quits), pw-dump
    appends further small arrays with these changes after the complete array –
    json.loads then reports "Extra data". Observed on the system (PipeWire 1.0.5).
    These updates are applied like in --monitor mode:
    {"id": N, "info": null} without a type = removed, otherwise added/replaced."""
    dec, pos, blocks = json.JSONDecoder(), 0, []
    raw = raw or "[]"
    while True:
        while pos < len(raw) and raw[pos].isspace():
            pos += 1
        if pos >= len(raw):
            break
        val, pos = dec.raw_decode(raw, pos)      # raises on genuinely broken JSON
        blocks.append(val)
    if not blocks:
        return []
    by_id: dict = {o.get("id"): o for o in blocks[0] if isinstance(o, dict)}
    for upd in blocks[1:]:
        for o in upd if isinstance(upd, list) else []:
            if not isinstance(o, dict):
                continue
            if o.get("info") is None and "type" not in o:
                by_id.pop(o.get("id"), None)
            else:
                by_id[o.get("id")] = o
    return list(by_id.values())


def parse_dump(raw: str) -> Graph:
    objs = _dump_objects(raw)
    nodes: dict[int, Node] = {}
    ports: list[Port] = []
    links: list[Link] = []
    # hardware devices: volume/mute live in the device's route
    # (node props show e.g. mute=False there although the route is muted)
    routes: dict[tuple[int, int], dict] = {}
    node_dev: dict[int, tuple[int, int]] = {}
    for o in objs:
        t = o.get("type", "")
        info = o.get("info") or {}
        props = info.get("props") or {}
        if t == "PipeWire:Interface:Device":
            for r in (info.get("params") or {}).get("Route") or []:
                if isinstance(r, dict) and "device" in r:
                    routes[(o["id"], r["device"])] = r.get("props") or {}
        elif t == "PipeWire:Interface:Node":
            mc = props.get("media.class", "")
            if not mc.startswith(("Audio/", "Stream/Output/Audio",
                                  "Stream/Input/Audio")):
                continue
            vol, mute = _volume_of((info.get("params") or {}).get("Props") or [])
            nodes[o["id"]] = Node(
                id=o["id"],
                name=props.get("node.name", ""),
                description=props.get("node.description")
                or props.get("node.nick", ""),
                media_class=mc,
                app_name=props.get("application.name", ""),
                media_name=props.get("media.name", ""),
                volume=vol, mute=mute,
            )
            try:
                node_dev[o["id"]] = (int(props["device.id"]), int(props["card.profile.device"]))
            except (KeyError, TypeError, ValueError):
                pass
        elif t == "PipeWire:Interface:Port":
            try:
                ports.append(Port(
                    id=o["id"],
                    node_id=int(props.get("node.id")),
                    direction=info.get("direction", ""),
                    name=props.get("port.name", ""),
                    channel=props.get("audio.channel", ""),
                    # pw-dump returns a JSON bool (True) here, not a string
                    monitor=str(props.get("port.monitor", False)).lower() == "true",
                ))
            except (TypeError, ValueError):
                continue
        elif t == "PipeWire:Interface:Link":
            links.append(Link(
                id=o["id"],
                out_node=info.get("output-node-id", -1),
                out_port=info.get("output-port-id", -1),
                in_node=info.get("input-node-id", -1),
                in_port=info.get("input-port-id", -1),
            ))
    for nid, key in node_dev.items():
        if key in routes and nid in nodes:
            vol, mute = _volume_of([routes[key]])
            if vol is not None:
                nodes[nid].volume = vol
            if mute is not None:
                nodes[nid].mute = mute
    for p in ports:
        n = nodes.get(p.node_id)
        if n is None:
            continue
        (n.in_ports if p.direction == "input" else n.out_ports).append(p)
    for n in nodes.values():
        n.in_ports.sort(key=lambda p: p.id)
        n.out_ports.sort(key=lambda p: p.id)
    return Graph(nodes, links, {p.id: p for p in ports if p.node_id in nodes})


def _volume_of(props_list: list) -> tuple[float | None, bool | None]:
    """channelVolumes are linear; displayed like wpctl = cube root."""
    for d in props_list:
        if not isinstance(d, dict):
            continue
        cv = d.get("channelVolumes")
        if cv:
            lin = max(0.0, sum(cv) / len(cv))
            m = d.get("mute")
            return lin ** (1 / 3), (bool(m) if m is not None else None)
    return None, None


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def read_graph() -> Graph:
    for attempt in range(4):
        r = _run(["pw-dump"])
        if r.returncode != 0:
            raise RuntimeError(f"pw-dump failed: {r.stderr.strip()}")
        try:
            return parse_dump(r.stdout)
        except json.JSONDecodeError:
            # broken JSON when objects vanish during the dump
            if attempt == 3:
                raise
            time.sleep(0.1)


# ------------------------------------------------------------------ links

def port_pairs(src: Node, dst: Node, dst_channels: list[str] | None = None) -> list[tuple[int, int]]:
    """Map source output ports to destination input ports by channel.
    dst_channels: only use these target inputs (e.g. ["RL", "RR"] for the
    priority input of the ducking block); source FL/FR -> 1st/2nd channel."""
    outs, ins = src.playable_out, dst.in_ports
    if dst_channels is not None:
        by = {i.channel: i for i in ins}
        ins = [by[c] for c in dst_channels if c in by]
        if not outs or not ins:
            return []
        if len(outs) == 1:
            return [(outs[0].id, i.id) for i in ins]
        order = {"FL": 0, "FR": 1, "MONO": 0}
        return [(o.id, ins[order.get(o.channel, k) % len(ins)].id) for k, o in enumerate(outs)]
    if not outs or not ins:
        return []
    if len(outs) == 1:
        return [(outs[0].id, i.id) for i in ins]          # mono -> all
    if len(ins) == 1:
        return [(o.id, ins[0].id) for o in outs]          # all -> mono
    by_ch = {i.channel: i for i in ins if i.channel}
    pairs = []
    for idx, o in enumerate(outs):
        i = by_ch.get(o.channel) or ins[idx % len(ins)]
        pairs.append((o.id, i.id))
    return pairs


def connect(graph: Graph, src_id: int, dst_id: int,
            dst_channels: list[str] | None = None) -> list[str]:
    errors = []
    existing = {(l.out_port, l.in_port) for l in graph.links}
    for op, ip in port_pairs(graph.nodes[src_id], graph.nodes[dst_id], dst_channels):
        if (op, ip) in existing:
            continue
        r = _run(["pw-link", str(op), str(ip)])
        if r.returncode != 0 and "File exists" not in r.stderr:
            errors.append(r.stderr.strip())
    return errors


def disconnect(graph: Graph, src_id: int, dst_id: int,
               dst_channels: list[str] | None = None) -> None:
    for l in graph.links:
        if l.out_node == src_id and l.in_node == dst_id and (
                dst_channels is None or graph.in_channel(l) in dst_channels):
            _run(["pw-link", "-d", str(l.id)])


def default_sink_name() -> str | None:
    r = _run(["pactl", "get-default-sink"])
    return r.stdout.strip() or None if r.returncode == 0 else None


# -------------------------------------------------------- virtual devices

def slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return VIRTUAL_PREFIX + (s or "mic")


def _find_module(sink_name: str) -> str | None:
    r = _run(["pactl", "list", "short", "modules"])
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[1] == "module-null-sink" \
                and re.search(rf"sink_name={re.escape(sink_name)}(\s|$)", parts[2]):
            return parts[0]
    return None


def create_virtual_mic(display_name: str, node_name: str | None = None) -> str:
    """Create a virtual microphone (Audio/Source/Virtual). Idempotent."""
    node_name = node_name or slug(display_name)
    if _find_module(node_name):
        return node_name
    # pipewire-pulse's module argument parser ends an unquoted value at the
    # first space -> the whole value must be quoted, with \" escaped inside.
    # Tested with PipeWire 1.0.5: spaces, apostrophes, umlauts ok;
    # " and \ cannot be passed through cleanly and are removed.
    desc = display_name.replace('"', "").replace("\\", "").strip() or node_name
    r = _run([
        "pactl", "load-module", "module-null-sink",
        "media.class=Audio/Source/Virtual",
        f"sink_name={node_name}",
        "channel_map=front-left,front-right",
        f'sink_properties="device.description=\\"{desc}\\""',
    ])
    if r.returncode != 0:
        raise RuntimeError(f"Could not create virtual mic: {r.stderr.strip()}")
    return node_name


def remove_virtual_mic(node_name: str) -> None:
    mid = _find_module(node_name)
    if mid:
        _run(["pactl", "unload-module", mid])


# ----------------------------------------------------------------- volume

MAX_VOLUME = 1.5        # 150 %, like pavucontrol (boost quiet mics)


def set_volume(node_id: int, volume: float) -> None:
    """Set the volume (1.0 = 100 %). For hardware devices wpctl writes to the
    route automatically, for streams/virtual devices to the node props."""
    v = min(max(volume, 0.0), MAX_VOLUME)
    _run(["wpctl", "set-volume", str(node_id), f"{v:.3f}"])


def set_mute(node_id: int, mute: bool) -> None:
    _run(["wpctl", "set-mute", str(node_id), "1" if mute else "0"])
