# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 benborofn-lgtm – Node-Router
"""Node-Router – Node-RED-style PipeWire patchbay.

Left:  input devices + application audio streams
Right: real output devices + virtual microphones created by this program
Drag from a source's port (right dot) to a target's port (left dot) to connect.
Click a wire and press Del (or double-click it) to disconnect.
"""
from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from pathlib import Path
from string import Template

from PySide6.QtCore import QEvent, QPointF, QProcess, QRectF, Qt, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import (QAction, QActionGroup, QBrush, QColor, QFont, QIcon,
                           QGuiApplication, QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsItem,
                               QGraphicsObject, QGraphicsPathItem,
                               QGraphicsScene, QGraphicsView, QHBoxLayout,
                               QInputDialog, QLabel, QMainWindow, QMenu,
                               QMessageBox, QSystemTrayIcon, QToolButton,
                               QVBoxLayout, QWidget,
                               QWidgetAction)

import deps
import fx as fxlib
import levels
import paths
import pw_backend as pw

# DIY_ROUTER_CONFIG=<file> uses a different config (e.g. for tests or a second profile)
CONFIG = paths.CONFIG
__version__ = "0.1.5"
APP_ID = "node-router"
REPO_URL = "https://github.com/benborofn-lgtm/Node-Router"
ICON = paths.RES / "icon.svg"
MAIN = Path(__file__).resolve()


def autostart_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / f"{APP_ID}.desktop"


def migrate_legacy_entries() -> None:
    """Replace menu/autostart entries from before the rename
    (diy-audio-router.desktop) with new ones – autostart stays enabled."""
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    for old, new, minimized in ((autostart_file().with_name(f"{paths.LEGACY_ID}.desktop"), autostart_file(), True),
                                (data / "applications" / f"{paths.LEGACY_ID}.desktop",
                                 data / "applications" / f"{APP_ID}.desktop", False)):
        if old.exists():
            try:
                if not new.exists():
                    new.parent.mkdir(parents=True, exist_ok=True)
                    new.write_text(desktop_entry(minimized))
                old.unlink()
            except OSError:
                pass


def desktop_entry(minimized: bool) -> str:
    """Desktop entry (app menu/autostart) for exactly this installation."""
    exe = paths.launch_command(minimized)
    return ("[Desktop Entry]\nType=Application\nName=Node-Router\n"
            "Comment=PipeWire patchbay with virtual microphones and effects\n"
            f"Exec={exe}\nIcon={paths.icon_path()}\nTerminal=false\n"
            "Categories=AudioVideo;Audio;Mixer;\n"
            + ("X-GNOME-Autostart-enabled=true\n" if minimized else ""))

NODE_W, NODE_H, PORT_R = 230, 82, 7
MARGIN, TOP, ROW = 16, 44, 96          # margin, list start (below column titles), row height
LEFT_X = MARGIN                          # right column: RouterView.col_x()
FX_W, FX_HEAD, FX_ROW = 214, 40, 26      # effect card: width, header, slider row
FX_PAD = 12                              # gap between effect card and mesh edge
# ---------------------------------------------------------------- themes
PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        # routing area / cards
        "bg": "#1e1f24", "grid": "#26282e", "node": "#2d3038", "node_ghost": "#272a31",
        "panel": "#191a1e", "border": "#454955", "divider": "#393c45",
        "text": "#e6e6e6", "sub": "#9aa0ac", "muted": "#5d626c",
        "src": "#4caf82", "app": "#5b9bd5", "sink": "#d58b4c", "virt": "#b07cd8", "fx": "#3cbfb0",
        "wire": "#c8c8c8", "sel": "#ffcc33", "ok": "#4caf82", "err": "#e05d5d",
        "track": "#1b1c20", "tick": "#5a5f6b", "knob": "#e6e6e6", "knob_ring": "#2d3038",
        # window / widgets
        "header": "#141518", "line": "#2a2c33", "btn_text": "#cfd3da",
        "btn_hover": "#24262c", "btn_hover_border": "#33363e", "btn_pressed": "#1c1d22",
        "menu_bg": "#1e1f24", "menu_border": "#33363e", "menu_sel": "#2d3038",
        "disabled": "#6b707b", "status_text": "#7c828e",
        "scroll_bg": "#191a1e", "scroll_handle": "#33363e",
        "primary": "#8f5fc0", "primary_border": "#a575d4",
        "primary_hover": "#9d6ccf", "primary_pressed": "#7d50ab",
    },
    "light": {
        "bg": "#f6f7f9", "grid": "#e7e9ed", "node": "#ffffff", "node_ghost": "#f1f2f4",
        "panel": "#eceef1", "border": "#c9cdd4", "divider": "#e3e6ea",
        "text": "#1f2328", "sub": "#636a75", "muted": "#b3b8c0",
        "src": "#2e9b68", "app": "#3577c0", "sink": "#c46a24", "virt": "#8c4fc4", "fx": "#14897e",
        "wire": "#7d8490", "sel": "#d99a00", "ok": "#2e9b68", "err": "#d04545",
        "track": "#e1e4e8", "tick": "#a3a9b2", "knob": "#ffffff", "knob_ring": "#8a919c",
        "header": "#ffffff", "line": "#dcdfe4", "btn_text": "#3a3f47",
        "btn_hover": "#eef0f3", "btn_hover_border": "#d5d9df", "btn_pressed": "#e3e6ea",
        "menu_bg": "#ffffff", "menu_border": "#d5d9df", "menu_sel": "#eef0f3",
        "disabled": "#a3a9b2", "status_text": "#6b717c",
        "scroll_bg": "#eceef1", "scroll_handle": "#c4c9d0",
        "primary": "#8f5fc0", "primary_border": "#7d50ab",
        "primary_hover": "#9d6ccf", "primary_pressed": "#7d50ab",
    },
}
COL: dict[str, QColor] = {k: QColor(v) for k, v in PALETTES["dark"].items()}
CURRENT_THEME = "dark"

STYLE_TEMPLATE = Template("""
QMainWindow { background: $header; }
#Header { background: $header; border-bottom: 1px solid $line; }
#Title { color: $text; font-size: 15px; font-weight: 600; }
#Status { color: $sub; font-size: 12px; }
QToolButton { color: $btn_text; background: transparent; border: 1px solid transparent;
              border-radius: 6px; padding: 6px 10px; font-size: 13px; }
QToolButton:hover { background: $btn_hover; border-color: $btn_hover_border; }
QToolButton:pressed { background: $btn_pressed; }
QToolButton::menu-indicator { image: none; width: 0; }
QToolButton#Primary { color: #ffffff; background: $primary; border-color: $primary_border;
                      font-weight: 600; padding: 6px 14px; }
QToolButton#Primary:hover { background: $primary_hover; }
QToolButton#Primary:pressed { background: $primary_pressed; }
QToolButton#Icon { font-size: 17px; padding: 3px 9px; }
QToolButton#Power { color: $ok; border-color: $btn_hover_border; padding: 5px 12px; }
QToolButton#Power:checked { color: #ffffff; background: $err; border-color: $err; }
QToolButton#Power:checked:hover { background: $err; }
QMenu { background: $menu_bg; color: $text; border: 1px solid $menu_border; padding: 4px;
        font-size: 13px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: $menu_sel; }
QMenu::item:disabled { color: $disabled; }
#FxEntry { border-radius: 4px; }
#FxEntry:hover { background: $menu_sel; }
QLabel#FxTitle { color: $text; font-size: 13px; }
QLabel#FxDesc { color: $sub; font-size: 11px; }
QLabel#FxTitle:disabled, QLabel#FxDesc:disabled { color: $disabled; }
QMenu::separator { height: 1px; background: $menu_border; margin: 4px 8px; }
QMenu::indicator { width: 12px; height: 12px; left: 4px; }
QToolTip { background: $menu_bg; color: $text; border: 1px solid $menu_border;
           border-radius: 4px; padding: 4px 8px; font-size: 12px; }
QStatusBar { background: $header; color: $status_text; border-top: 1px solid $line; }
QStatusBar QLabel, QStatusBar { padding-left: 8px; }
QStatusBar::item { border: 0; }
QScrollBar:vertical { background: $scroll_bg; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $scroll_handle; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
""")


def set_palette(name: str) -> str:
    """Switch colors used by painting code (COL), return the stylesheet."""
    global CURRENT_THEME
    name = name if name in PALETTES else "dark"
    CURRENT_THEME = name
    COL.update({k: QColor(v) for k, v in PALETTES[name].items()})
    return STYLE_TEMPLATE.substitute(PALETTES[name])


def emph(c: QColor) -> QColor:
    """Hover emphasis: lighter in dark mode, darker in light mode."""
    return c.darker(125) if CURRENT_THEME == "light" else c.lighter(130)


class MenuEntry(QWidget):
    """Menu entry with title + description below (instead of a tooltip: Qt
    tooltips in menus got stuck or clipped when moving directly between
    entries)."""

    def __init__(self, title: str, desc: str, action: QWidgetAction, menu: QMenu):
        super().__init__()
        self.action, self.menu = action, menu
        self.setObjectName("FxEntry")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor if action.isEnabled() else Qt.ArrowCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 7); lay.setSpacing(1)
        t = QLabel(title); t.setObjectName("FxTitle")
        d = QLabel(desc); d.setObjectName("FxDesc"); d.setWordWrap(True); d.setFixedWidth(290)
        lay.addWidget(t); lay.addWidget(d)
        self.setEnabled(action.isEnabled())

    _pressed = False

    def mousePressEvent(self, e):
        self._pressed = e.button() == Qt.LeftButton
        e.accept()

    def mouseReleaseEvent(self, e):
        # only trigger if the press happened here too – otherwise releasing the
        # double-click that opened the menu would pick an entry
        pressed, self._pressed = self._pressed, False
        if pressed and self.isEnabled() and self.rect().contains(e.position().toPoint()):
            self.menu.close()
            self.action.trigger()


class Header(QFrame):
    """Header bar: title + live status on the left, actions on the right."""

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.setObjectName("Header")
        self.setFixedHeight(56)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(MARGIN, 0, MARGIN - 4, 0)
        lay.setSpacing(6)

        texts = QVBoxLayout(); texts.setSpacing(1)
        texts.setContentsMargins(0, 8, 0, 8)
        self.title = QLabel("Node-Router"); self.title.setObjectName("Title")
        self.status = QLabel(); self.status.setObjectName("Status")
        texts.addWidget(self.title); texts.addWidget(self.status)
        lay.addLayout(texts)
        lay.addStretch(1)

        power = QToolButton()
        power.setObjectName("Power"); power.setCheckable(True)
        power.setChecked(win.cfg.disabled)
        power.toggled.connect(lambda off: win.set_router_disabled(off))
        self.power_button = power
        self._power_text(win.cfg.disabled)
        lay.addWidget(power)
        lay.addSpacing(4)
        refresh = QToolButton(text="⟳", toolTip="Refresh (F5)")
        refresh.setObjectName("Icon")
        refresh.clicked.connect(lambda: win.refresh(force=True))
        more = QToolButton(text="⋯", toolTip="More actions")
        more.setObjectName("Icon")
        more.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(more)
        design = menu.addMenu("Theme")
        group = QActionGroup(design); group.setExclusive(True)
        self.theme_actions = {}
        for key, text in (("dark", "Dark"), ("light", "Light"), ("system", "Follow system")):
            a = design.addAction(text, lambda k=key: win.set_theme(k))
            a.setCheckable(True); group.addAction(a)
            self.theme_actions[key] = a
        self.theme_actions.get(win.cfg.theme, self.theme_actions["dark"]).setChecked(True)
        menu.addSeparator()
        menu.addAction("Reset sorting", win.reset_layout)
        self.hidden_menu = menu.addMenu("Hidden")
        self.hidden_menu.aboutToShow.connect(lambda: self._fill_hidden(win))
        menu.aboutToShow.connect(lambda: self.hidden_menu.setTitle(
            f"Hidden ({len(win.cfg.ignored)})"))
        menu.addSeparator()
        self.autostart_action = menu.addAction("Start at login")
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart_file().exists())
        self.autostart_action.toggled.connect(win.set_autostart)
        menu.addAction("Open config folder", win.open_config_dir)
        menu.addSeparator()
        menu.addAction("About Node-Router", win.show_about)
        more.setMenu(menu)
        add = QToolButton(text="＋  Virtual microphone")
        add.setObjectName("Primary"); add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(win.add_virtual)
        for b in (refresh, more):
            b.setCursor(Qt.PointingHandCursor)
            lay.addWidget(b)
        lay.addSpacing(6)
        lay.addWidget(add)
        self.add_button, self.refresh_button, self.more_button = add, refresh, more
        self.set_status(None)

    def _power_text(self, disabled: bool):
        self.power_button.setText("○  Disabled" if disabled else "●  Active")
        self.power_button.setToolTip(
            "Router is off: its connections are removed, effects stopped. Click to enable."
            if disabled else "Click to disable the router (the program stays open)")

    def _fill_hidden(self, win: "MainWindow"):
        m = self.hidden_menu
        m.clear()
        if not win.cfg.ignored:
            a = m.addAction("Nothing hidden"); a.setEnabled(False)
            return
        for key, label in sorted(win.cfg.ignored.items(), key=lambda kv: kv[1].lower()):
            m.addAction(f"{label}  –  show again",
                        lambda k=key: win.unignore_node(k))
        m.addSeparator()
        m.addAction("Show all again", lambda: [win.unignore_node(k) for k in list(win.cfg.ignored)])

    def set_status(self, graph: "pw.Graph | None", ok: bool = True, ignored=(), disabled=False):
        if disabled and ok:
            dot, text = COL["err"].name(), "Router disabled  ·  its connections removed, effects stopped"
        elif not ok:
            dot, text = COL["err"].name(), "PipeWire not reachable"
        elif graph is None:
            dot, text = COL["sub"].name(), "connecting …"
        else:
            nodes = [n for n in graph.nodes.values() if n.key not in ignored]
            left = sum(1 for n in nodes if n.is_left)
            right = sum(1 for n in nodes if n.is_right)
            ids = {n.id for n in nodes if n.is_left or n.is_right or n.is_effect}
            links = len({(l.out_node, l.in_node) for l in graph.links
                         if l.out_node in ids and l.in_node in ids})
            dot = COL["ok"].name()
            def n(k, one, many):
                return f"{k} {one if k == 1 else many}"
            text = (f"PipeWire connected  ·  {n(left, 'source', 'sources')}  ·  "
                    f"{n(right, 'target', 'targets')}  ·  {n(links, 'connection', 'connections')}")
        self.status.setText(f'<span style="color:{dot}">●</span>&nbsp; {text}')


# ======================================================================
# Config
# ======================================================================
class Config:
    def __init__(self) -> None:
        self.virtual_mics: list[dict] = []     # {"name": node_name, "label": str}
        self.routes: list[list[str]] = []      # [src_key, dst_key] made by user
        # [src_key, dst_key] disconnected by the user -> removed again if
        # WirePlumber re-creates it (e.g. when the app restarts)
        self.blocked: list[list[str]] = []
        # order of both lists (node keys, top -> bottom). Also contains keys of
        # nodes that are currently absent, so an app reappears at its old place.
        self.order: dict[str, list[str]] = {"left": [], "right": []}
        # display data of recently seen nodes (key -> name, class, side), so vanished
        # nodes stay as greyed-out cards – also after a restart
        self.known: dict[str, dict] = {}
        # hidden nodes (key -> display name): never shown again,
        # even when the app plays sound again (e.g. libcanberra)
        self.ignored: dict[str, str] = {}
        self.theme = "dark"                    # "dark" | "light" | "system"
        # effect blocks in the mesh: {"id","type","params":{..},"x": 0..1 (relative
        # to the mesh width), "y": px}
        self.effects: list[dict] = []
        self.disabled = False                  # on/off button: everything disabled
        if CONFIG.exists():
            try:
                d = json.loads(CONFIG.read_text())
                self.virtual_mics = d.get("virtual_mics", [])
                self.routes = d.get("routes", [])
                self.blocked = d.get("blocked", [])
                o = d.get("order", {})
                self.order = {"left": list(o.get("left", [])), "right": list(o.get("right", []))}
                self.known = d.get("known_nodes", {})
                self.ignored = d.get("ignored", {})
                self.theme = d.get("theme", "dark")
                self.effects = [e for e in d.get("effects", []) if e.get("type") in fxlib.TYPES]
                self.disabled = bool(d.get("disabled", False))
            except (json.JSONDecodeError, OSError) as e:
                print(f"config.json ignored: {e}", file=sys.stderr)

    def save(self) -> None:
        CONFIG.write_text(json.dumps({
            "virtual_mics": self.virtual_mics,
            "routes": self.routes,
            "blocked": self.blocked,
            "order": self.order,
            "known_nodes": self.known,
            "ignored": self.ignored,
            "theme": self.theme,
            "effects": self.effects,
            "disabled": self.disabled,
        }, indent=2))

    def forget(self, key: str) -> None:
        """Remove key from the lists + display data (routes are kept)."""
        for side in ("left", "right"):
            self.order[side] = [k for k in self.order[side] if k != key]
        self.known.pop(key, None)


# ======================================================================
# Graphics items
# ======================================================================
class PortItem(QGraphicsItem):
    def __init__(self, node_item, is_output: bool, pos: QPointF | None = None):
        super().__init__(node_item)
        self.node_item, self.is_output = node_item, is_output
        self.group: str | None = None            # input group (ducking: main/prio)
        self.setPos(pos if pos is not None else QPointF(NODE_W if is_output else 0, NODE_H / 2))
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CrossCursor)
        self._hover = False

    def boundingRect(self) -> QRectF:
        r = PORT_R + 3
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, p: QPainter, *_):
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(COL["bg"], 2))
        c = emph(self.node_item.color) if self._hover else self.node_item.color
        p.setBrush(c)
        p.drawEllipse(QPointF(0, 0), PORT_R, PORT_R)

    def hoverEnterEvent(self, e):
        self._hover = True; self.update()

    def hoverLeaveEvent(self, e):
        self._hover = False; self.update()

    def scene_center(self) -> QPointF:
        return self.mapToScene(QPointF(0, 0))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.scene().views()[0].begin_drag(self)
            e.accept()


class VolumeItem(QGraphicsItem):
    """Volume slider + mute button in a node card (0-150 %)."""
    Y, H = 54, 20                      # row inside the card

    def __init__(self, node_item: "NodeItem"):
        super().__init__(node_item)
        self.node_item = node_item
        self.x0 = 18 if node_item.left else 14
        self.w = NODE_W - 36
        self.value = node_item.node.volume or 0.0
        self.muted = bool(node_item.node.mute)
        self.dragging = False
        self._pending: float | None = None
        self._sending = False
        self._hold_until = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptHoverEvents(True)
        self._hover = False
        self.meter_on = False           # level meter running for this card
        self.meter = 0.0                # 0..1 on a dB scale (-60 … 0 dBFS)
        self.clip = False
        self.setToolTip("Volume · mouse wheel: ±5 % · double-click: 100 %")

    # geometry
    def boundingRect(self) -> QRectF:
        return QRectF(self.x0, self.Y, self.w, self.H)

    def mute_rect(self) -> QRectF:
        return QRectF(self.x0, self.Y + 2, 16, 16)

    def track(self) -> tuple[float, float]:
        return self.x0 + 24, self.x0 + self.w - 42

    def _x_for(self, v: float) -> float:
        a, b = self.track()
        return a + (b - a) * min(max(v, 0.0), pw.MAX_VOLUME) / pw.MAX_VOLUME

    def _v_for(self, x: float) -> float:
        a, b = self.track()
        v = (x - a) / (b - a) * pw.MAX_VOLUME
        if abs(v - 1.0) < 0.03:        # snap slightly to 100 %
            v = 1.0
        return min(max(v, 0.0), pw.MAX_VOLUME)

    def set_level(self, level: float, clip: bool, on: bool) -> None:
        if (level, clip, on) != (self.meter, self.clip, self.meter_on):
            self.meter, self.clip, self.meter_on = level, clip, on
            self.update()

    # state from PipeWire
    def sync_from_node(self):
        n = self.node_item.node
        self.setVisible(n.volume is not None)
        if self.dragging:
            return                      # re-synced on release anyway
        wait = self._hold_until - time.monotonic()
        if wait > 0:
            # own change still in flight -> re-sync afterwards, otherwise an external
            # change arriving during this window would stay invisible
            QTimer.singleShot(int(wait * 1000) + 20, self.sync_from_node)
            return
        self.value = n.volume or 0.0
        self.muted = bool(n.mute)
        self.update()

    def paint(self, p: QPainter, *_):
        p.setRenderHint(QPainter.Antialiasing)
        c = self.node_item.color
        cy = self.Y + self.H / 2
        # speaker icon
        m = self.mute_rect()
        icon = COL["err"] if self.muted else (COL["text"] if self._hover else COL["sub"])
        sp = QPainterPath()
        sp.moveTo(m.left() + 1, cy - 3); sp.lineTo(m.left() + 5, cy - 3)
        sp.lineTo(m.left() + 9, cy - 7); sp.lineTo(m.left() + 9, cy + 7)
        sp.lineTo(m.left() + 5, cy + 3); sp.lineTo(m.left() + 1, cy + 3); sp.closeSubpath()
        p.setPen(Qt.NoPen); p.setBrush(icon); p.drawPath(sp)
        p.setPen(QPen(icon, 1.4)); p.setBrush(Qt.NoBrush)
        if self.muted:
            p.drawLine(QPointF(m.left() + 11, cy - 3), QPointF(m.left() + 16, cy + 3))
            p.drawLine(QPointF(m.left() + 16, cy - 3), QPointF(m.left() + 11, cy + 3))
        else:
            p.drawArc(QRectF(m.left() + 6, cy - 4, 8, 8), -60 * 16, 120 * 16)
            if self.value > 0.5:
                p.drawArc(QRectF(m.left() + 5, cy - 7, 13, 14), -60 * 16, 120 * 16)
        # track
        a, b = self.track()
        p.setPen(Qt.NoPen); p.setBrush(COL["track"])
        p.drawRoundedRect(QRectF(a, cy - 2, b - a, 4), 2, 2)
        kx = self._x_for(self.value)
        fill = COL["muted"] if self.muted else c
        p.setBrush(fill); p.drawRoundedRect(QRectF(a, cy - 2, kx - a, 4), 2, 2)
        # level meter: thin bar below the track (signal peak, -60 … 0 dBFS)
        if self.meter_on:
            # LED-style segments: card color, yellow above -6 dBFS, red above -1 dBFS
            # (all lit segments red after clipping)
            my, seg, gap = cy + 6, 3.0, 1.5
            n = int((b - a + gap) // (seg + gap))
            for k in range(n):
                pos = (k + 1) / n
                lit = pos <= self.meter + 1e-9
                if not lit:
                    col = COL["track"]
                elif self.clip or pos > 0.983:
                    col = COL["err"]
                elif pos > 0.9:
                    col = COL["sel"]
                else:
                    col = c
                p.fillRect(QRectF(a + k * (seg + gap), my, seg, 3), col)
        # 100 % mark
        tx = self._x_for(1.0)
        p.setPen(QPen(COL["tick"], 1))
        p.drawLine(QPointF(tx, cy - 5), QPointF(tx, cy + 5))
        # knob
        p.setPen(QPen(COL["knob_ring"], 1.5)); p.setBrush(COL["knob"] if not self.muted else COL["muted"])
        p.drawEllipse(QPointF(kx, cy), 6 if (self._hover or self.dragging) else 5,
                      6 if (self._hover or self.dragging) else 5)
        # percent
        f = QFont(); f.setPointSize(8); p.setFont(f)
        p.setPen(COL["err"] if self.muted else (c if self.value > 1.0 else COL["sub"]))
        p.drawText(QRectF(b + 6, self.Y, self.x0 + self.w - b - 6, self.H),
                   Qt.AlignRight | Qt.AlignVCenter,
                   "muted" if self.muted else f"{round(self.value * 100)} %")

    # interaction
    def hoverEnterEvent(self, e):
        self._hover = True; self.update()

    def hoverLeaveEvent(self, e):
        self._hover = False; self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            e.ignore(); return
        e.accept()
        if self.mute_rect().adjusted(-3, -3, 3, 3).contains(e.pos()):
            self.muted = not self.muted
            self._hold_until = time.monotonic() + 1.0
            pw.set_mute(self.node_item.node.id, self.muted)
            self.update(); return
        self.dragging = True
        self._set(self._v_for(e.pos().x()))

    def mouseMoveEvent(self, e):
        if self.dragging:
            self._set(self._v_for(e.pos().x()))

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            self._flush()
            self._hold_until = time.monotonic() + 1.0
            QTimer.singleShot(1050, self.sync_from_node)
            self.update()

    def mouseDoubleClickEvent(self, e):
        if not self.mute_rect().adjusted(-3, -3, 3, 3).contains(e.pos()):
            self._set(1.0); self._flush()
            self._hold_until = time.monotonic() + 1.0
        e.accept()

    def wheelEvent(self, e):
        step = 0.05 if e.delta() > 0 else -0.05
        self._set(round((self.value + step) * 20) / 20)
        self._hold_until = time.monotonic() + 1.0
        e.accept()

    def _set(self, v: float):
        self.value = min(max(v, 0.0), pw.MAX_VOLUME)
        self._pending = self.value
        self.update()
        if not self._sending:           # at most every 60 ms to wpctl
            self._sending = True
            QTimer.singleShot(60, self._flush)

    def _flush(self):
        self._sending = False
        if self._pending is not None:
            v, self._pending = self._pending, None
            pw.set_volume(self.node_item.node.id, v)


def ghost_node(key: str, meta: dict) -> pw.Node:
    """Placeholder node for an app/device that is currently absent."""
    return pw.Node(id=-(abs(hash(key)) % 10**9) - 1, name=meta.get("name", ""),
                   description=meta.get("description", ""),
                   media_class=meta.get("media_class", ""),
                   app_name=meta.get("app_name", ""), media_name="")


class NodeItem(QGraphicsObject):
    def __init__(self, node: pw.Node, left: bool, ghost: bool = False):
        super().__init__()
        self.node, self.left, self.ghost = node, left, ghost
        # only movable vertically (sorting within the list), not selectable
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(Qt.OpenHandCursor)
        self.port = PortItem(self, is_output=left)
        self.wires: list[WireItem] = []
        self.dragging = False
        self.setZValue(1)
        self.vol = VolumeItem(self)
        self.vol.sync_from_node()
        if ghost:
            self.setOpacity(0.42)
            self.setToolTip("Currently inactive (e.g. video paused). Saved connections "
                            "are restored as soon as it is back.")

    @property
    def side(self) -> str:
        return "left" if self.left else "right"

    # common connection interface (like EffectItem)
    @property
    def out_port(self) -> "PortItem":
        return self.port

    @property
    def in_port(self) -> "PortItem":
        return self.port

    def port_for(self, output: bool) -> "PortItem | None":
        return self.port if self.port.is_output == output else None

    def live_out(self) -> pw.Node | None:
        return None if self.ghost or not self.left else self.node

    def live_in(self) -> pw.Node | None:
        return None if self.ghost or self.left else self.node

    def out_key(self) -> str | None:
        return self.node.key if self.left else None

    def in_key(self, group: str | None = None) -> str | None:
        return None if self.left else self.node.key

    def all_in_keys(self) -> list[tuple[str, str | None]]:
        return [] if self.left else [(self.node.key, None)]

    def in_port_for(self, group: str | None) -> "PortItem":
        return self.port

    def channels_for(self, group: str | None) -> list[str] | None:
        return None

    def group_for_channel(self, ch: str) -> str | None:
        return None

    @property
    def color(self) -> QColor:
        n = self.node
        if n.is_virtual_mic:
            return COL["virt"]
        if n.is_stream:
            return COL["app"]
        return COL["src"] if self.left else COL["sink"]

    def update_node(self, node: pw.Node) -> None:
        self.node = node
        self.vol.sync_from_node()
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-2, -2, NODE_W + 4, NODE_H + 4)

    def paint(self, p: QPainter, *_):
        p.setRenderHint(QPainter.Antialiasing)
        sel = self.dragging
        p.setPen(QPen(COL["sel"] if sel else COL["border"], 2 if sel else 1))
        if self.ghost and not sel:
            p.setPen(QPen(COL["border"], 1, Qt.DashLine))
        p.setBrush(COL["node_ghost"] if self.ghost else COL["node"])
        p.drawRoundedRect(QRectF(0, 0, NODE_W, NODE_H), 6, 6)
        # colored stripe like Node-RED
        stripe = QRectF(0 if self.left else NODE_W - 10, 0, 10, NODE_H)
        path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, NODE_W, NODE_H), 6, 6)
        stripe_c = COL["muted"] if self.ghost else self.color
        p.save(); p.setClipPath(path); p.fillRect(stripe, stripe_c); p.restore()
        x0 = 18 if self.left else 14
        w = NODE_W - 36
        f = QFont(); f.setBold(True); f.setPointSize(10); p.setFont(f)
        p.setPen(COL["text"])
        p.drawText(QRectF(x0, 6, w, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(self.node.label, Qt.ElideRight, int(w)))
        f.setBold(False); f.setPointSize(8); p.setFont(f)
        p.setPen(COL["sub"])
        if self.ghost:
            sub = "Paused / inactive"
        else:
            ch = len(self.node.playable_out if self.left else self.node.in_ports)
            sub = f"{self.node.sublabel} · {ch}ch"
        p.drawText(QRectF(x0, 28, w, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(sub, Qt.ElideRight, int(w)))
        if self.vol.isVisible():
            p.setPen(QPen(COL["divider"], 1))
            p.drawLine(QPointF(x0, 51.5), QPointF(x0 + w, 51.5))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            # x fixed to the column, y only within the list
            view = self.scene().views()[0] if self.scene() else None
            if not view:
                return value
            n = max(1, view.column_count(self.side))
            y = min(max(value.y(), TOP - ROW / 2), TOP + (n - 0.5) * ROW)
            return QPointF(view.col_x(self.side), y)
        if change == QGraphicsItem.ItemPositionHasChanged:
            for w in self.wires:
                w.update_path()
            if self.dragging:
                self.scene().views()[0].preview_reorder(self)
        return super().itemChange(change, value)

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.setZValue(3); self.setCursor(Qt.ClosedHandCursor); self.update()

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if self.dragging:
            self.dragging = False
            self.setZValue(1); self.setCursor(Qt.OpenHandCursor); self.update()
            self.scene().views()[0].commit_reorder(self)


class ParamSlider(QGraphicsItem):
    """Slider for an effect parameter (label · track · value)."""
    LABEL_W, VAL_W, H = 58, 56, FX_ROW

    def __init__(self, card: "EffectItem", spec: dict, value: float, y: float):
        super().__init__(card)
        self.card, self.spec, self.value = card, spec, float(value)
        self.setPos(0, y)
        self.dragging = False
        self._hover = False
        self._pending: float | None = None
        self._sending = False
        self._final = QTimer(singleShot=True, interval=500, timeout=self._commit)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        tip = "Drag · mouse wheel: fine · double-click: default"
        if spec.get("restart"):
            tip += "\nChanging this briefly restarts the block (connections are kept)"
        self.setToolTip(tip)

    # scale
    def track(self) -> tuple[float, float]:
        return 12 + self.LABEL_W, FX_W - 12 - self.VAL_W

    def _norm(self, v: float) -> float:
        lo, hi = self.spec["min"], self.spec["max"]
        if self.spec.get("log"):
            return (math.log(v) - math.log(lo)) / (math.log(hi) - math.log(lo))
        return (v - lo) / (hi - lo)

    def _denorm(self, t: float) -> float:
        lo, hi = self.spec["min"], self.spec["max"]
        t = min(max(t, 0.0), 1.0)
        if self.spec.get("log"):
            return math.exp(math.log(lo) + t * (math.log(hi) - math.log(lo)))
        return lo + t * (hi - lo)

    def _round(self, v: float) -> float:
        u = self.spec["unit"]
        step = {"dB": 0.5, "s": 0.1}.get(u, 1.0)
        v = round(v / step) * step
        return min(max(v, self.spec["min"]), self.spec["max"])

    def text(self) -> str:
        v, u = self.value, self.spec["unit"]
        if u == "dB":
            return f"{v:+.1f} dB" if v else "0 dB"
        if u == "s":
            return f"{v:.1f} s"
        if u == "Hz" and v >= 1000:
            return f"{v / 1000:.2f} kHz"
        if u == ":1":
            return f"{v:.0f}:1"
        return f"{v:.0f} {u}"

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, FX_W, self.H)

    def paint(self, p: QPainter, *_):
        p.setRenderHint(QPainter.Antialiasing)
        cy = self.H / 2
        f = QFont(); f.setPointSize(8); p.setFont(f)
        p.setPen(COL["sub"])
        p.drawText(QRectF(12, 0, self.LABEL_W, self.H), Qt.AlignLeft | Qt.AlignVCenter, self.spec["label"])
        a, b = self.track()
        p.setPen(Qt.NoPen); p.setBrush(COL["track"])
        p.drawRoundedRect(QRectF(a, cy - 2, b - a, 4), 2, 2)
        kx = a + (b - a) * self._norm(self.value)
        # for ±dB fill from the center
        zx = a + (b - a) * self._norm(0.0) if self.spec["min"] < 0 < self.spec["max"] else a
        p.setBrush(COL["fx"])
        p.drawRoundedRect(QRectF(min(zx, kx), cy - 2, abs(kx - zx), 4), 2, 2)
        if zx != a:
            p.setPen(QPen(COL["tick"], 1)); p.drawLine(QPointF(zx, cy - 5), QPointF(zx, cy + 5))
        r = 6 if (self._hover or self.dragging) else 5
        p.setPen(QPen(COL["knob_ring"], 1.5)); p.setBrush(COL["knob"])
        p.drawEllipse(QPointF(kx, cy), r, r)
        p.setPen(COL["text"] if self.dragging else COL["sub"])
        p.drawText(QRectF(b + 6, 0, FX_W - 12 - b - 6, self.H), Qt.AlignRight | Qt.AlignVCenter, self.text())

    # interaction
    def hoverEnterEvent(self, e):
        self._hover = True; self.update()

    def hoverLeaveEvent(self, e):
        self._hover = False; self.update()

    def _from_x(self, x: float) -> float:
        a, b = self.track()
        return self._round(self._denorm((x - a) / (b - a)))

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            e.ignore(); return
        e.accept()
        self.dragging = True
        self._set(self._from_x(e.pos().x()))

    def mouseMoveEvent(self, e):
        if self.dragging:
            self._set(self._from_x(e.pos().x()))

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            self._commit()

    def mouseDoubleClickEvent(self, e):
        self._set(self.spec["default"]); self._commit(); e.accept()

    def wheelEvent(self, e):
        up = e.delta() > 0
        u = self.spec["unit"]
        if self.spec.get("log"):
            v = self.value * (1.06 if up else 1 / 1.06)
        else:
            v = self.value + ({"dB": 0.5, "ms": 10, "%": 5, "s": 0.1}.get(u, 1) * (1 if up else -1))
        self._set(self._round(v))
        self._final.start()            # save/restart only after a short pause
        e.accept()

    def _set(self, v: float):
        self.value = v
        self.update()
        if self.spec.get("restart"):
            return                     # takes effect on release (restart)
        self._pending = v
        if not self._sending:          # at most every 60 ms to pw-cli
            self._sending = True
            QTimer.singleShot(60, self._flush)

    def _flush(self):
        self._sending = False
        if self._pending is not None:
            v, self._pending = self._pending, None
            self.card.param_changed(self.spec["key"], v, final=False)

    def _commit(self):
        self._pending = None
        self.card.param_changed(self.spec["key"], self.value, final=True)


class EffectItem(QGraphicsObject):
    """Freely movable effect block in the mesh (input left, output right)."""

    def __init__(self, fx: dict):
        super().__init__()
        self.fx = fx
        self.spec = fxlib.TYPES[fx["type"]]
        self.in_node: pw.Node | None = None
        self.out_node: pw.Node | None = None
        self.restarting = False
        self.wires: list = []
        self.dragging = False
        self.ghost = False
        self.groups = fxlib.input_groups(fx["type"])
        self.multi = len(self.groups) > 1
        self.in_rows = len(self.groups) * self.IN_ROW + 4 if self.multi else 0
        self.h = FX_HEAD + self.in_rows + len(self.spec["params"]) * FX_ROW + 8
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(Qt.OpenHandCursor)
        self.setZValue(2)
        self.setToolTip(self.spec["hint"])
        self.in_ports: dict[str | None, PortItem] = {}
        for i, g in enumerate(self.groups):
            y = FX_HEAD + 2 + i * self.IN_ROW + self.IN_ROW / 2 if self.multi else FX_HEAD / 2
            port = PortItem(self, False, QPointF(0, y))
            port.group = g["group"]
            if self.multi:
                port.setToolTip(f"Input \"{g['label']}\"")
            self.in_ports[g["group"]] = port
        self.out_port = PortItem(self, True, QPointF(FX_W, FX_HEAD / 2))
        self.sliders = {}
        for i, ps in enumerate(self.spec["params"]):
            self.sliders[ps["key"]] = ParamSlider(self, ps, fx["params"].get(ps["key"], ps["default"]),
                                                  FX_HEAD + self.in_rows + i * FX_ROW)

    IN_ROW = 22

    @property
    def in_port(self) -> "PortItem":
        return next(iter(self.in_ports.values()))

    def in_port_for(self, group: str | None) -> "PortItem":
        return self.in_ports.get(group) or self.in_port

    def channels_for(self, group: str | None) -> list[str] | None:
        return fxlib.channels_for(self.fx["type"], group) if self.multi else None

    def group_for_channel(self, ch: str) -> str | None:
        for g in self.groups:
            if g["channels"] and ch in g["channels"]:
                return g["group"]
        return self.groups[0]["group"]

    @property
    def color(self) -> QColor:
        return COL["fx"]

    @property
    def running(self) -> bool:
        return self.in_node is not None and self.out_node is not None and not self.restarting

    # connection interface (like NodeItem)
    def port_for(self, output: bool, near: QPointF | None = None) -> "PortItem":
        if output:
            return self.out_port
        if near is None or not self.multi:
            return self.in_port
        return min(self.in_ports.values(), key=lambda p: abs(p.scene_center().y() - near.y()))

    def live_out(self) -> pw.Node | None:
        return self.out_node if self.running else None

    def live_in(self) -> pw.Node | None:
        return self.in_node if self.running else None

    def out_key(self) -> str:
        return "fx:" + fxlib.node_names(self.fx["id"])[1]

    def in_key(self, group: str | None = None) -> str:
        base = "fx:" + fxlib.node_names(self.fx["id"])[0]
        return f"{base}#{group}" if group and self.multi else base

    def all_in_keys(self) -> list[tuple[str, str | None]]:
        return [(self.in_key(g["group"]), g["group"]) for g in self.groups]

    def boundingRect(self) -> QRectF:
        return QRectF(-2, -2, FX_W + 4, self.h + 4)

    def paint(self, p: QPainter, *_):
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, FX_W, self.h)
        p.setPen(QPen(COL["sel"] if self.dragging else COL["border"], 2 if self.dragging else 1))
        p.setBrush(COL["node"])
        p.drawRoundedRect(r, 6, 6)
        path = QPainterPath(); path.addRoundedRect(r, 6, 6)
        p.save(); p.setClipPath(path)
        p.fillRect(QRectF(0, 0, FX_W, 4), COL["fx"] if self.running else COL["muted"])
        p.restore()
        f = QFont(); f.setBold(True); f.setPointSize(10); p.setFont(f)
        p.setPen(COL["text"])
        p.drawText(QRectF(14, 6, FX_W - 28, 18), Qt.AlignLeft | Qt.AlignVCenter, self.spec["title"])
        f.setBold(False); f.setPointSize(8); p.setFont(f)
        p.setPen(COL["sub"])
        view = self.scene().views()[0] if self.scene() else None
        if view and view.win.cfg.disabled:
            state = "disabled"
        else:
            state = "Effect" if self.running else ("restarting …" if self.restarting else "starting …")
        p.drawText(QRectF(14, 22, FX_W - 28, 14), Qt.AlignLeft | Qt.AlignVCenter, state)
        p.setPen(QPen(COL["divider"], 1))
        p.drawLine(QPointF(12, FX_HEAD - 0.5), QPointF(FX_W - 12, FX_HEAD - 0.5))
        if self.multi:                          # input labels
            f.setPointSize(8); p.setFont(f)
            for i, g in enumerate(self.groups):
                y = FX_HEAD + 2 + i * self.IN_ROW
                p.setPen(COL["text"])
                p.drawText(QRectF(14, y, FX_W - 28, self.IN_ROW), Qt.AlignLeft | Qt.AlignVCenter,
                           "◂ " + g["label"])
            p.setPen(QPen(COL["divider"], 1))
            yl = FX_HEAD + self.in_rows - 1.5
            p.drawLine(QPointF(12, yl), QPointF(FX_W - 12, yl))

    def param_changed(self, key: str, value: float, final: bool):
        view = self.scene().views()[0] if self.scene() else None
        if view:
            view.win.set_effect_param(self, key, value, final)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            return self.scene().views()[0].clamp_effect(self, value)
        if change == QGraphicsItem.ItemPositionHasChanged:
            for w in self.wires:
                w.update_path()
        return super().itemChange(change, value)

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.setZValue(4); self.setCursor(Qt.ClosedHandCursor); self.update()

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if self.dragging:
            self.dragging = False
            self.setZValue(2); self.setCursor(Qt.OpenHandCursor); self.update()
            self.scene().views()[0].effect_moved(self)


def bezier(a: QPointF, b: QPointF) -> QPainterPath:
    path = QPainterPath(a)
    dx = max(60.0, abs(b.x() - a.x()) * 0.5)
    path.cubicTo(a + QPointF(dx, 0), b - QPointF(dx, 0), b)
    return path


class WireItem(QGraphicsPathItem):
    def __init__(self, src, dst, planned: bool = False, group: str | None = None):
        super().__init__()
        self.src, self.dst, self.group = src, dst, group
        self.planned = planned          # saved route, no PipeWire link (yet)
        if planned:
            self.setToolTip("Saved connection – created as soon as both sides are active")
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setZValue(0)
        self.setAcceptHoverEvents(True)
        self._hover = False
        src.wires.append(self); dst.wires.append(self)
        self.update_path()

    def update_path(self):
        self.setPath(bezier(self.src.out_port.scene_center(),
                            self.dst.in_port_for(self.group).scene_center()))

    def shape(self):
        from PySide6.QtGui import QPainterPathStroker
        s = QPainterPathStroker(); s.setWidth(12)
        return s.createStroke(self.path())

    def paint(self, p, *_):
        p.setRenderHint(QPainter.Antialiasing)
        base = COL["sub"] if self.planned else self.src.color
        c = COL["sel"] if self.isSelected() else (emph(base) if self._hover else base)
        p.setPen(QPen(c, 3 if (self.isSelected() or self._hover) else 2.2,
                      Qt.DashLine if self.planned else Qt.SolidLine))
        p.setBrush(Qt.NoBrush)
        p.drawPath(self.path())

    def hoverEnterEvent(self, e):
        self._hover = True; self.update()

    def hoverLeaveEvent(self, e):
        self._hover = False; self.update()

    def detach(self):
        for n in (self.src, self.dst):
            if self in n.wires:
                n.wires.remove(self)

    def mouseDoubleClickEvent(self, e):
        self.scene().views()[0].delete_wire(self)


# ======================================================================
# View / controller
# ======================================================================
class RouterView(QGraphicsView):
    def __init__(self, win: "MainWindow"):
        self.scene_ = QGraphicsScene()
        super().__init__(self.scene_)
        self.win = win
        self.setRenderHints(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        # fixed view: scene = viewport pixels, no zoom, vertical scrolling only
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setBackgroundBrush(COL["bg"])
        self.node_items: dict[int, NodeItem] = {}
        self.fx_items: dict[str, EffectItem] = {}
        self.wires: list[WireItem] = []
        self._drag_from: PortItem | None = None
        self._temp: QGraphicsPathItem | None = None
        # the mesh must fit at least one effect card
        self.setMinimumWidth(2 * (NODE_W + 2 * MARGIN) + FX_W + 2 * FX_PAD + 8)

    # ---------------- background grid
    def drawBackground(self, p: QPainter, rect: QRectF):
        p.fillRect(rect, COL["panel"])
        gl, gr = self.grid_span()
        area = QRectF(gl, rect.top(), gr - gl, rect.height()).intersected(rect)
        if area.isEmpty():
            return
        p.fillRect(area, COL["bg"])
        p.setPen(QPen(COL["grid"], 1))
        g = 24
        x = gl + g
        while x < gr:
            if area.left() <= x <= area.right():
                p.drawLine(x, area.top(), x, area.bottom())
            x += g
        y = int(area.top()) - int(area.top()) % g
        while y < area.bottom():
            p.drawLine(gl, y, gr, y); y += g
        p.setPen(QPen(COL["border"], 1))
        p.drawLine(gl, area.top(), gl, area.bottom())
        p.drawLine(gr, area.top(), gr, area.bottom())

    def drawForeground(self, p: QPainter, rect: QRectF):
        if self.win.cfg.disabled:            # dimmed + notice
            veil = QColor(COL["bg"]); veil.setAlpha(165)
            p.fillRect(rect, veil)
            vis = self.mapToScene(self.viewport().rect()).boundingRect()
            gl, gr = self.grid_span()
            box = QRectF(gl + 10, vis.center().y() - 40, gr - gl - 20, 80)
            f = QFont(); f.setPointSize(13); f.setBold(True); p.setFont(f)
            p.setPen(COL["err"])
            p.drawText(QRectF(box.x(), box.y(), box.width(), 40), Qt.AlignCenter, "Router disabled")
            f.setPointSize(9); f.setBold(False); p.setFont(f); p.setPen(COL["sub"])
            p.drawText(QRectF(box.x(), box.y() + 36, box.width(), 40), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                       "Its connections are removed, effects stopped.\nClick \"Disabled\" at the top to enable it again.")
        # column titles above the lists
        f = QFont(); f.setPointSize(8); f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        p.setFont(f); p.setPen(COL["sub"])
        for side, text in (("left", "SOURCES · INPUTS & APPS"),
                           ("right", "TARGETS · OUTPUTS & MICS")):
            p.drawText(QRectF(self.col_x(side) + 2, 12, NODE_W, 20),
                       Qt.AlignLeft | Qt.AlignVCenter, text)

    # ---------------- fixed geometry
    def col_x(self, side: str) -> float:
        return LEFT_X if side == "left" else self.viewport().width() - MARGIN - NODE_W

    def grid_span(self) -> tuple[float, float]:
        """Routing area between the lists (incl. ports)."""
        return (LEFT_X + NODE_W + MARGIN, self.col_x("right") - MARGIN)

    def _update_scene_rect(self):
        rows = max([self.column_count(s) for s in ("left", "right")] + [0])
        h = max(self.viewport().height(), TOP + rows * ROW + MARGIN,
                *[it.pos().y() + it.h + MARGIN for it in self.fx_items.values()])
        self.scene_.setSceneRect(0, 0, self.viewport().width(), h)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_scene_rect()
        self.layout_columns()
        self.layout_effects()
        for w in self.wires:
            w.update_path()

    # ---------------- effects in the mesh
    def _fx_x_range(self) -> tuple[float, float]:
        gl, gr = self.grid_span()
        lo = gl + FX_PAD
        return lo, max(lo, gr - FX_PAD - FX_W)

    def effect_pos(self, fx: dict) -> QPointF:
        lo, hi = self._fx_x_range()
        return QPointF(lo + (hi - lo) * min(max(fx.get("x", 0.5), 0.0), 1.0), fx.get("y", TOP))

    def clamp_effect(self, item: "EffectItem", value: QPointF) -> QPointF:
        lo, hi = self._fx_x_range()
        y_max = max(8.0, self.viewport().height() - item.h - 8)
        return QPointF(min(max(value.x(), lo), hi), min(max(value.y(), 8.0), y_max))

    def layout_effects(self):
        for it in self.fx_items.values():
            if not it.dragging:
                it.setPos(self.effect_pos(it.fx))

    def effect_moved(self, item: "EffectItem"):
        lo, hi = self._fx_x_range()
        item.fx["x"] = (item.pos().x() - lo) / (hi - lo) if hi > lo else 0.5
        item.fx["y"] = item.pos().y()
        self.win.cfg.save()

    def _sync_effects(self, graph: pw.Graph, cfg: Config):
        by_name = {n.name: n for n in graph.nodes.values() if n.is_effect}
        wanted = {fx["id"]: fx for fx in cfg.effects}
        for fid in list(self.fx_items):
            if fid not in wanted:
                it = self.fx_items.pop(fid)
                for w in list(it.wires):
                    w.detach()
                self.scene_.removeItem(it)
        for fid, fx in wanted.items():
            it = self.fx_items.get(fid)
            if it is None:
                it = EffectItem(fx)
                self.fx_items[fid] = it
                self.scene_.addItem(it)
                it.setPos(self.effect_pos(fx))
            nin, nout = fxlib.node_names(fid)
            it.in_node, it.out_node = by_name.get(nin), by_name.get(nout)
            it.restarting = fid in self.win.restarting
            it.update()

    # ---------------- sync scene with graph
    def sync(self, graph: pw.Graph, cfg: Config):
        wanted = {nid: n for nid, n in graph.nodes.items()
                  if (n.is_left or n.is_right) and n.key not in cfg.ignored}
        # placeholders for known keys that are currently missing (e.g. paused video)
        live_keys = {n.key for n in wanted.values()}
        ghost_side: dict[int, str] = {}
        for side in ("left", "right"):
            for key in cfg.order[side]:
                meta = cfg.known.get(key)
                if (key in live_keys or not meta or meta.get("side") != side
                        or key in cfg.ignored
                        or str(meta.get("name", "")).startswith(pw.FX_PREFIX)):
                    continue                 # effect nodes are never list entries
                g = ghost_node(key, meta)
                if g.key != key:             # inconsistent entry -> do not show
                    continue
                wanted[g.id] = g
                ghost_side[g.id] = side
        for nid in list(self.node_items):
            if nid not in wanted:
                item = self.node_items.pop(nid)
                for w in list(item.wires):
                    w.detach()
                self.scene_.removeItem(item)
        for nid, n in wanted.items():
            if nid in self.node_items:
                self.node_items[nid].update_node(n)
                continue
            ghost = nid < 0
            left = ghost_side[nid] == "left" if ghost else n.is_left
            item = NodeItem(n, left=left, ghost=ghost)
            self.node_items[nid] = item
            self.scene_.addItem(item)
        changed = self._add_unknown_keys(cfg)
        for it in self.node_items.values():     # remember display data of current nodes
            if it.ghost:
                continue
            n = it.node
            meta = {"side": it.side, "name": n.name, "description": n.description,
                    "media_class": n.media_class, "app_name": n.app_name}
            if cfg.known.get(n.key) != meta:
                cfg.known[n.key] = meta; changed = True
        if changed:
            cfg.save()
        self._sync_effects(graph, cfg)
        self._update_scene_rect()
        self.layout_columns()
        self._rebuild_wires(graph)

    # ---------------- two sortable lists
    def column_count(self, side: str) -> int:
        return sum(1 for i in self.node_items.values() if i.side == side)

    def _add_unknown_keys(self, cfg: Config) -> bool:
        """Append new nodes to the end of their list (default sorting:
        left apps before devices, right devices before virtual mics)."""
        changed = False
        defaults = {
            "left": lambda i: (not i.node.is_stream, i.node.label.lower()),
            "right": lambda i: (i.node.is_virtual_mic, i.node.label.lower()),
        }
        for side, key in defaults.items():
            order = cfg.order[side]
            fresh = sorted((i for i in self.node_items.values()
                            if i.side == side and not i.ghost and i.node.key not in order),
                           key=key)
            for it in fresh:
                if it.node.key not in order:
                    order.append(it.node.key); changed = True
        return changed

    def _sorted_column(self, side: str) -> list[NodeItem]:
        order = self.win.cfg.order[side]
        idx = {k: n for n, k in enumerate(order)}
        items = [i for i in self.node_items.values() if i.side == side]
        return sorted(items, key=lambda i: (idx.get(i.node.key, len(order)), i.node.id))

    def layout_columns(self):
        for side in ("left", "right"):
            for row, it in enumerate(self._sorted_column(side)):
                if not it.dragging:
                    it.setPos(self.col_x(side), TOP + row * ROW)

    def _target_row(self, item: NodeItem) -> int:
        n = self.column_count(item.side)
        return min(max(round((item.pos().y() - TOP) / ROW), 0), n - 1)

    def preview_reorder(self, item: NodeItem):
        """While dragging, the other entries make room."""
        others = [i for i in self._sorted_column(item.side) if i is not item]
        others.insert(self._target_row(item), item)
        x = self.col_x(item.side)
        for row, it in enumerate(others):
            if it is not item and it.pos().y() != TOP + row * ROW:
                it.setPos(x, TOP + row * ROW)

    def commit_reorder(self, item: NodeItem):
        side = item.side
        others = [i for i in self._sorted_column(side) if i is not item]
        row = self._target_row(item)
        others.insert(row, item)
        # rebuild the full list: visible keys in their new order,
        # absent ones (e.g. closed apps) keep their relative place
        order = self.win.cfg.order[side]
        visible = []
        for it in others:
            if it.node.key not in visible:
                visible.append(it.node.key)
        vis = set(visible)
        slots = iter(visible)
        new_order = [next(slots) if k in vis else k for k in order]
        new_order += [k for k in slots]          # in case something was not in order yet
        self.win.cfg.order[side] = list(dict.fromkeys(new_order))
        self.win.cfg.save()
        self.layout_columns()

    def _rebuild_wires(self, graph: pw.Graph):
        for w in self.wires:
            w.detach(); self.scene_.removeItem(w)
        self.wires.clear()
        items = list(self.node_items.values()) + list(self.fx_items.values())
        # PipeWire node id -> card (output or input side)
        out_owner, in_owner = {}, {}
        for it in items:
            if (n := it.live_out()) is not None:
                out_owner[n.id] = it
            if (n := it.live_in()) is not None:
                in_owner[n.id] = it
        drawn = set()
        for l in graph.links:
            si, di = out_owner.get(l.out_node), in_owner.get(l.in_node)
            if not si or not di or si is di:
                continue
            grp = di.group_for_channel(graph.in_channel(l))
            if (id(si), id(di), grp) not in drawn:
                drawn.add((id(si), id(di), grp))
                w = WireItem(si, di, group=grp)
                self.scene_.addItem(w); self.wires.append(w)
        # saved routes where one side is currently inactive
        # (greyed-out card, effect still starting): dashed
        by_out, by_in = {}, {}
        for it in items:
            if (k := it.out_key()) is not None:
                by_out.setdefault(k, it)
            for k, grp in it.all_in_keys():
                by_in.setdefault(k, (it, grp))
        for sk, dk in self.win.cfg.routes:
            si, (di, grp) = by_out.get(sk), by_in.get(dk, (None, None))
            if not si or not di or si is di or (id(si), id(di), grp) in drawn:
                continue
            if si.live_out() is None or di.live_in() is None:
                drawn.add((id(si), id(di), grp))
                w = WireItem(si, di, planned=True, group=grp)
                self.scene_.addItem(w); self.wires.append(w)

    # ---------------- drag-to-connect
    def begin_drag(self, port: PortItem):
        self._drag_from = port
        self._temp = QGraphicsPathItem()
        self._temp.setPen(QPen(COL["wire"], 2, Qt.DashLine))
        self._temp.setZValue(5)
        self.scene_.addItem(self._temp)

    def mouseMoveEvent(self, e):
        if self._drag_from and self._temp:
            a = self._drag_from.scene_center()
            b = self.mapToScene(e.position().toPoint())
            self._temp.setPath(bezier(a, b) if self._drag_from.is_output else bezier(b, a))
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._drag_from:
            g = self.scene_.mouseGrabberItem()
            if g:
                g.ungrabMouse()
            start = self._drag_from
            self.scene_.removeItem(self._temp)
            self._drag_from = self._temp = None
            target = None
            for it in self.scene_.items(self.mapToScene(e.position().toPoint())):
                if isinstance(it, PortItem):
                    target = it; break
                while it is not None and not isinstance(it, (NodeItem, EffectItem)):
                    it = it.parentItem()
                if it is not None:           # released on the card: nearest matching port
                    sp = self.mapToScene(e.position().toPoint())
                    target = (it.port_for(not start.is_output, sp) if isinstance(it, EffectItem)
                              else it.port_for(not start.is_output))
                    break
            if (target and target.is_output != start.is_output
                    and target.node_item is not start.node_item):
                src, dst = (start, target) if start.is_output else (target, start)
                self.win.connect_nodes(src.node_item, dst.node_item, dst.group)
            return
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e):
        if isinstance(self.itemAt(e.position().toPoint()), (VolumeItem, ParamSlider)):
            super().wheelEvent(e)       # -> slider.wheelEvent
            return
        # no zoom; the wheel only scrolls vertically (if lists are longer than the window)
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - e.angleDelta().y() // 2)
        e.accept()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for it in list(self.scene_.selectedItems()):
                if isinstance(it, WireItem):
                    self.delete_wire(it)
            return
        super().keyPressEvent(e)

    def delete_wire(self, w: WireItem):
        self.win.disconnect_nodes(w.src, w.dst, w.group)

    def in_mesh(self, view_pos) -> bool:
        gl, gr = self.grid_span()
        return gl < self.mapToScene(view_pos).x() < gr

    def add_menu(self, menu: QMenu, view_pos):
        sp = self.mapToScene(view_pos)
        for kind, spec in fxlib.TYPES.items():
            ok, why = fxlib.available(kind)
            a = QWidgetAction(menu)
            a.setText(spec["title"]); a.setEnabled(ok)
            a.triggered.connect(lambda _=False, k=kind: self.win.add_effect(k, sp))
            a.setDefaultWidget(MenuEntry(spec["title"], spec["hint"] if ok else why, a, menu))
            menu.addAction(a)

    def mouseDoubleClickEvent(self, e):
        if self.win.cfg.disabled:
            return
        if (e.button() == Qt.LeftButton and self.itemAt(e.position().toPoint()) is None
                and self.in_mesh(e.position().toPoint())):
            m = QMenu(self)
            t = m.addAction("Add block"); t.setEnabled(False)
            m.addSeparator()
            self.add_menu(m, e.position().toPoint())
            m.exec(e.globalPosition().toPoint())
            return
        super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, e):
        it = self.itemAt(e.pos())
        while it and not isinstance(it, (NodeItem, WireItem, EffectItem)):
            it = it.parentItem()
        m = QMenu(self)
        if self.win.cfg.disabled:
            m.addAction("Enable router", lambda: self.win.header.power_button.setChecked(False))
            m.exec(e.globalPos())
            return
        if isinstance(it, EffectItem):
            m.addAction("Reset to defaults", lambda: self.win.reset_effect(it))
            m.addAction("Disconnect all",
                        lambda: [self.delete_wire(w) for w in list(it.wires)])
            m.addSeparator()
            m.addAction("Remove block", lambda: self.win.remove_effect(it))
        elif isinstance(it, WireItem):
            m.addAction("Disconnect", lambda: self.delete_wire(it))
        elif isinstance(it, NodeItem) and it.ghost:
            m.addAction("Remove from list", lambda: self.win.forget_node(it.node.key))
            m.addAction("Ignore (never show again)", lambda: self.win.ignore_node(it))
        elif isinstance(it, NodeItem):
            n = it.node
            if n.is_virtual_mic:
                m.addAction("Rename…", lambda: self.win.rename_virtual(n))
                m.addAction("Delete virtual mic", lambda: self.win.remove_virtual(n))
            m.addAction("Disconnect all",
                        lambda: [self.delete_wire(w) for w in list(it.wires)])
            if not n.is_virtual_mic:     # own mics are deleted rather than hidden
                m.addSeparator()
                m.addAction("Ignore (never show again)", lambda: self.win.ignore_node(it))
        else:
            if self.in_mesh(e.pos()):
                self.add_menu(m.addMenu("Add block"), e.pos())
            m.addAction("Add virtual microphone…", self.win.add_virtual)
        m.exec(e.globalPos())


# ======================================================================
# Main window
# ======================================================================
class MainWindow(QMainWindow):
    def __init__(self, tray: bool = False, check_system: bool = False):
        super().__init__()
        self.setWindowTitle("Node-Router")
        self.setWindowIcon(QIcon(str(ICON)))
        self._quitting = False                   # True: really quit (not just to the tray)
        self._shutting = False                   # do not restart the monitor anymore
        self._vm_tried: dict[str, float] = {}    # virtual mics: last creation attempt
        self.resize(1000, 700)
        self.cfg = Config()
        self.graph = pw.Graph({}, [])
        self._sig = None
        self.restarting: set[str] = set()       # effect ids currently restarting
        self._deactivate_pending = False         # set after loading the config
        self._spawned: dict[str, float] = {}     # effect id -> start time
        self.view = RouterView(self)
        self.setCentralWidget(self.view)
        self._deactivate_pending = self.cfg.disabled
        self.view.setInteractive(not self.cfg.disabled)

        self.apply_theme()
        # "Follow system": apply KDE/GNOME switching live
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            lambda *_: self.cfg.theme == "system" and self.apply_theme())
        self.header = Header(self)
        self.setMenuWidget(self.header)
        self.addAction(QAction("Refresh", self, shortcut="F5",
                               triggered=lambda: self.refresh(force=True)))
        self.view.setFrameShape(QFrame.NoFrame)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().showMessage(
            "Drag port → port to connect · double-click the mesh: add block · "
            "click a wire + Del to disconnect")

        for vm in self.cfg.virtual_mics:          # restore virtual devices
            try:
                pw.create_virtual_mic(vm["label"], vm["name"])
            except RuntimeError as e:
                self.error(str(e))

        levels.kill_stale()                      # recorders of a crashed earlier instance
        self.meters = levels.LevelMeters(self._on_level, self)
        self.proc = QProcess(self)
        self.proc.finished.connect(self._dump_done)
        self._pending = False
        # fallback poll; normally triggered by pw-dump --monitor
        self.timer = QTimer(self, interval=1000, timeout=self.refresh)
        self.timer.start()
        # event driven: every graph change -> re-read after 50 ms (debounced).
        # Important for blocked routes: the WP link is removed after ~0.1 s instead of ≤1 s.
        self.debounce = QTimer(self, singleShot=True, interval=50, timeout=self.refresh)
        self._mon_buf = ""
        self._mon_types: dict[int, str] = {}      # id -> type (removals arrive without a type)
        self.mon = QProcess(self)
        self.mon.readyReadStandardOutput.connect(self._mon_event)
        self.mon.finished.connect(self._mon_finished)
        self._start_mon()
        self.tray = self._make_tray() if tray and QSystemTrayIcon.isSystemTrayAvailable() else None
        self._tray_hint_shown = False
        self.refresh(force=True)
        if check_system:                         # PipeWire & co. missing? -> notice with command
            QTimer.singleShot(300, self.check_system)

    def check_system(self) -> list[str]:
        probs = deps.problems()
        if probs:
            box = QMessageBox(QMessageBox.Warning, "Node-Router – something is missing",
                              deps.help_text(probs), parent=self)
            cmd = deps.install_command()
            if cmd:
                copy = box.addButton("Copy command", QMessageBox.ActionRole)
                copy.clicked.disconnect()
                copy.clicked.connect(lambda: QApplication.clipboard().setText(
                    f"{cmd} && {deps.SERVICES}"))
            box.addButton(QMessageBox.Close)
            box.setTextInteractionFlags(Qt.TextSelectableByMouse)
            box.open()
            self._deps_box = box
            self.statusBar().showMessage("System packages are missing – see the notice")
        return probs

    # ---------------- background operation
    def _make_tray(self) -> QSystemTrayIcon:
        t = QSystemTrayIcon(QIcon(str(ICON)), self)
        t.setToolTip("Node-Router")
        m = QMenu(self)
        m.addAction("Open window", self.show_window)
        m.addSeparator()
        self.tray_active = m.addAction("Router active")
        self.tray_active.setCheckable(True)
        self.tray_active.setChecked(not self.cfg.disabled)
        self.tray_active.toggled.connect(lambda on: self.set_router_disabled(not on))
        m.addSeparator()
        m.addAction("Quit", self.quit_app)
        t.setContextMenu(m)
        t.activated.connect(lambda r: self.toggle_window()
                            if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        t.show()
        return t

    def show_window(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def toggle_window(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show_window()

    def quit_app(self):
        self._quitting = True
        self.close()
        QApplication.quit()

    def set_autostart(self, on: bool):
        f = autostart_file()
        if on:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(desktop_entry(minimized=True))
        else:
            f.unlink(missing_ok=True)

    # ---------------- PipeWire restart
    def _start_mon(self):
        self._mon_buf = ""
        self._mon_types.clear()
        self.mon.start("pw-dump", ["--monitor", "--no-colors"])

    def _mon_finished(self, *_):
        """pw-dump --monitor ends when PipeWire restarts/crashes -> restart it
        after a short pause and re-read everything."""
        if self._shutting:
            return
        QTimer.singleShot(1000, lambda: (not self._shutting) and (self._start_mon(), self.refresh(force=True)))

    def _ensure_virtual_mics(self, g: pw.Graph):
        """Re-create virtual mics when they are missing (e.g. after a restart of
        PipeWire/pipewire-pulse) – also while disabled."""
        names = {n.name for n in g.nodes.values()}
        now = time.monotonic()
        for vm in self.cfg.virtual_mics:
            if vm["name"] in names or now - self._vm_tried.get(vm["name"], -1e9) < 5:
                continue
            self._vm_tried[vm["name"]] = now
            try:
                pw.create_virtual_mic(vm["label"], vm["name"])
            except RuntimeError as e:
                print(f"virtual mic {vm['name']}: {e}", file=sys.stderr)

    _MON_RELEVANT = ("PipeWire:Interface:Node", "PipeWire:Interface:Port",
                     "PipeWire:Interface:Link")

    def _mon_event(self):
        """pw-dump --monitor writes one JSON array per change. Only node/port/link
        changes trigger a re-read – client events do not, otherwise every own
        pw-dump (= new client) would trigger the next one."""
        self._mon_buf += bytes(self.mon.readAllStandardOutput()).decode("utf-8", "replace")
        dec, relevant = json.JSONDecoder(), False
        while True:
            s = self._mon_buf.lstrip()
            if not s:
                self._mon_buf = ""; break
            try:
                objs, end = dec.raw_decode(s)
            except json.JSONDecodeError:
                self._mon_buf = s; break          # block not complete yet
            self._mon_buf = s[end:]
            for o in objs if isinstance(objs, list) else []:
                oid, t = o.get("id"), o.get("type")
                if o.get("info") is None and not t:          # removed
                    t = self._mon_types.pop(oid, "")
                elif t:
                    self._mon_types[oid] = t
                relevant |= t in self._MON_RELEVANT
        if relevant:
            self.debounce.start()

    # ---------------- level meters
    def _sync_meters(self):
        """Meters only while the window can be seen and the router is active
        (a meter on a microphone keeps that microphone open)."""
        if self._shutting:
            return
        self.meters.enabled = (self.isVisible() and not self.isMinimized()
                               and not self.cfg.disabled)
        wanted = [it.node for it in self.view.node_items.values() if not it.ghost]
        self.meters.sync(self.graph, wanted)

    def _on_level(self, nid: int, level: float, clip: bool):
        it = self.view.node_items.get(nid)
        if it is not None and not it.ghost:
            it.vol.set_level(level, clip, nid in self.meters.meters)

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._sync_meters)

    def hideEvent(self, e):
        super().hideEvent(e)
        QTimer.singleShot(0, self._sync_meters)

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange:
            QTimer.singleShot(0, self._sync_meters)

    def closeEvent(self, e):
        if self.tray is not None and not self._quitting:
            # closing the window = background; routes keep being maintained
            e.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.showMessage("Node-Router keeps running",
                                      "Open or quit it via the icon in the system tray.",
                                      QIcon(str(ICON)), 4000)
            return
        if self.tray is not None:
            self.tray.hide()
        # do nothing anymore once the window is closed (effect processes keep running)
        self._shutting = True
        self.meters.stop_all()
        self.timer.stop(); self.debounce.stop()
        self.proc.finished.disconnect(self._dump_done)
        self.mon.kill(); self.mon.waitForFinished(1000)
        super().closeEvent(e)

    # ---------------- polling
    def refresh(self, force: bool = False):
        if force:
            self._sig = None
        if self.proc.state() == QProcess.NotRunning:
            self.proc.start("pw-dump", [])
        else:
            self._pending = True                  # change during a running dump

    def _dump_done(self, code, _status):
        if self._pending:
            self._pending = False
            QTimer.singleShot(0, self.refresh)
        if code != 0:
            self.header.set_status(None, ok=False)
            return
        raw = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        try:
            g = pw.parse_dump(raw)
        except json.JSONDecodeError:
            # genuinely broken pw-dump output -> try again shortly
            self._bad_dumps = getattr(self, "_bad_dumps", 0) + 1
            if self._bad_dumps <= 5:
                QTimer.singleShot(150, self.refresh)
            return
        self._bad_dumps = 0
        self.graph = g
        self.header.set_status(g, ignored=self.cfg.ignored, disabled=self.cfg.disabled)
        self._ensure_virtual_mics(g)
        if self.cfg.disabled:
            # enforce/restore nothing; when starting in the disabled state
            # clean up once (effects might still be running)
            if self._deactivate_pending:
                self._deactivate_pending = False
                self._deactivate()
            removed = False
        else:
            self._ensure_effects(g)
            removed = self._enforce_blocked()
            self._restore_routes()
        if removed:
            # the graph is stale now -> do not show it, the next poll (≤1 s) re-reads.
            # No immediate refresh(): with a permanently failing pw-link -d this
            # would create an endless loop of pw-dump calls.
            self._sig = None
            return
        sig = g.signature()
        if sig != self._sig:
            self._sig = sig
            self.view.sync(g, self.cfg)
        self._sync_meters()

    def _nodes_by_key(self) -> dict[str, list[pw.Node]]:
        by_key: dict[str, list[pw.Node]] = {}
        for n in self.graph.nodes.values():
            by_key.setdefault(n.key, []).append(n)
        return by_key

    def _enforce_blocked(self) -> bool:
        """Remove links the user disconnected but WirePlumber re-created
        (WP 0.4 does not relink at runtime, only when the stream reappears)."""
        if not self.cfg.blocked:
            return False
        by_key = self._nodes_by_key()
        linked = self._linked()
        removed = False
        for sk, dk in self.cfg.blocked:
            base, chans = self._route_target(dk)
            for s in by_key.get(sk, []):
                for d in by_key.get(base, []):
                    if self._is_linked(linked, s.id, d.id, chans):
                        pw.disconnect(self.graph, s.id, d.id, chans)
                        removed = True
        return removed

    def _linked(self) -> set[tuple[int, int, str]]:
        return {(l.out_node, l.in_node, self.graph.in_channel(l)) for l in self.graph.links}

    @staticmethod
    def _is_linked(linked, s: int, d: int, chans: list[str] | None) -> bool:
        return any(x[0] == s and x[1] == d and (chans is None or x[2] in chans) for x in linked)

    def _route_target(self, key: str) -> tuple[str, list[str] | None]:
        """'fx:diy_fx_<id>_in#prio' -> ('fx:diy_fx_<id>_in', ['RL', 'RR'])."""
        base, _, grp = key.partition("#")
        if not grp:
            return base, None
        for fx in self.cfg.effects:
            if base == "fx:" + fxlib.node_names(fx["id"])[0]:
                return base, fxlib.channels_for(fx["type"], grp)
        return base, None

    def _restore_routes(self):
        """Re-apply user routes when nodes (re)appear, e.g. app restarted."""
        by_key = self._nodes_by_key()
        linked = self._linked()
        for sk, dk in self.cfg.routes:
            base, chans = self._route_target(dk)
            for s in by_key.get(sk, []):
                for d in by_key.get(base, []):
                    if ((s.is_left or s.is_fx_out) and (d.is_right or d.is_fx_in)
                            and not self._is_linked(linked, s.id, d.id, chans)):
                        pw.connect(self.graph, s.id, d.id, chans)

    # ---------------- actions
    def connect_nodes(self, src, dst, group: str | None = None):
        """src: card with an output (left list or effect), dst: with an input.
        If one side is currently inactive (greyed out, effect starting), only the
        route is saved – the link follows as soon as both are there."""
        sn, dn = src.live_out(), dst.live_in()
        if sn is not None and dn is not None:
            errs = pw.connect(self.graph, sn.id, dn.id, dst.channels_for(group))
            if errs:
                self.error("\n".join(errs))
        r = [src.out_key(), dst.in_key(group)]
        if r in self.cfg.blocked:
            self.cfg.blocked.remove(r)
        if r not in self.cfg.routes:
            self.cfg.routes.append(r)
        self.cfg.save()
        self.refresh(force=True)

    def disconnect_nodes(self, src, dst, group: str | None = None):
        sn, dn = src.live_out(), dst.live_in()
        if sn is not None and dn is not None:
            pw.disconnect(self.graph, sn.id, dn.id, dst.channels_for(group))
        r = [src.out_key(), dst.in_key(group)]
        if r in self.cfg.routes:
            self.cfg.routes.remove(r)
        if r not in self.cfg.blocked:
            self.cfg.blocked.append(r)
        self.cfg.save()
        self.refresh(force=True)

    # ---------------- on/off
    def set_router_disabled(self, disabled: bool):
        if disabled == self.cfg.disabled:
            return
        self.cfg.disabled = disabled
        self.cfg.save()
        self.header._power_text(disabled)
        if self.header.power_button.isChecked() != disabled:
            self.header.power_button.setChecked(disabled)
        self.view.setInteractive(not disabled)
        if getattr(self, "tray", None) is not None and self.tray_active.isChecked() == disabled:
            self.tray_active.setChecked(not disabled)
        if disabled:
            self._deactivate()
        else:
            self._spawned.clear()                # restart effects right away
        self.header.set_status(self.graph if self.graph.nodes else None,
                               ignored=self.cfg.ignored, disabled=disabled)
        self.view.resetCachedContent(); self.view.scene_.update(); self.view.viewport().update()
        self.refresh(force=True)

    def _deactivate(self):
        """Disconnect own routes, stop effects, reconnect blocked default output
        (app -> default speaker). Virtual mics stay."""
        g = self.graph
        by_key = self._nodes_by_key()
        linked = self._linked()
        for sk, dk in self.cfg.routes:
            base, chans = self._route_target(dk)
            for s in by_key.get(sk, []):
                for d in by_key.get(base, []):
                    if self._is_linked(linked, s.id, d.id, chans):
                        pw.disconnect(g, s.id, d.id, chans)
        default = pw.default_sink_name()
        if default:
            for sk, dk in self.cfg.blocked:
                if not sk.startswith("app:") or dk != f"dev:{default}":
                    continue                     # only what WirePlumber itself would do
                for s in by_key.get(sk, []):
                    for d in by_key.get(dk, []):
                        if s.is_left and not self._is_linked(linked, s.id, d.id, None):
                            pw.connect(g, s.id, d.id)
        ids = [fx["id"] for fx in self.cfg.effects]
        self._bg(lambda: [fxlib.kill(i) for i in ids])

    # ---------------- effects
    def _ensure_effects(self, g: pw.Graph):
        """Start missing effect processes (first start, after a reboot, if one
        crashed). Running ones are reused."""
        names = {n.name for n in g.nodes.values() if n.is_effect}
        now = time.monotonic()
        for fx in self.cfg.effects:
            fid = fx["id"]
            if fid in self.restarting or all(n in names for n in fxlib.node_names(fid)):
                continue
            if now - self._spawned.get(fid, -1e9) < 5:     # currently starting
                continue
            if fxlib.running_pid(fid):
                if now - self._spawned.get(fid, -1e9) < 15:
                    continue
                fxlib.kill(fid)                            # stuck -> restart
            self._spawned[fid] = now
            self._bg(fxlib.spawn, dict(fx, params=dict(fx["params"])))

    def _bg(self, fn, *args, done=None):
        """Slow work (generate impulse response, stop/start a process) in the
        background; Qt objects are not touched there."""
        def run():
            try:
                fn(*args)
            finally:
                if done:
                    done()
        threading.Thread(target=run, daemon=True).start()

    def add_effect(self, kind: str, scene_pos: QPointF):
        fx = {"id": fxlib.new_id(), "type": kind, "params": fxlib.defaults(kind)}
        lo, hi = self.view._fx_x_range()
        x = scene_pos.x() - FX_W / 2
        fx["x"] = min(max((x - lo) / (hi - lo), 0.0), 1.0) if hi > lo else 0.5
        fx["y"] = max(8.0, scene_pos.y() - FX_HEAD / 2)
        self.cfg.effects.append(fx)
        self.cfg.save()
        self._spawned[fx["id"]] = time.monotonic()
        self._bg(fxlib.spawn, dict(fx, params=dict(fx["params"])))
        self.refresh(force=True)

    def remove_effect(self, item: "EffectItem"):
        fid = item.fx["id"]
        keys = {item.out_key()} | {k for k, _ in item.all_in_keys()}
        self.cfg.effects = [f for f in self.cfg.effects if f["id"] != fid]
        self.cfg.routes = [r for r in self.cfg.routes if not keys & set(r)]
        self.cfg.blocked = [r for r in self.cfg.blocked if not keys & set(r)]
        self.cfg.save()
        self.restarting.add(fid)                     # do not start again
        def done():
            self.restarting.discard(fid)
        self._bg(lambda: (fxlib.kill(fid), fxlib.delete_files(fid)), done=done)
        self.refresh(force=True)

    def set_effect_param(self, item: "EffectItem", key: str, value: float, final: bool):
        fx = item.fx
        fx["params"][key] = value
        spec = next(p for p in item.spec["params"] if p["key"] == key)
        if spec.get("restart"):
            if final:
                self.restart_effect(item)
        elif item.running:
            pairs = fxlib.controls(fx["type"], fx["params"])
            fxlib.set_controls(item.in_node.id, pairs)
        if final:
            self.cfg.save()

    def restart_effect(self, item: "EffectItem"):
        fid = item.fx["id"]
        if fid in self.restarting:
            return
        self.restarting.add(fid)
        item.restarting = True; item.update()
        snapshot = dict(item.fx, params=dict(item.fx["params"]))
        def work():
            fxlib.kill(fid)
            fxlib.spawn(snapshot)
        def done():
            self._spawned[fid] = time.monotonic()
            self.restarting.discard(fid)
        self._bg(work, done=done)
        self.refresh(force=True)

    def reset_effect(self, item: "EffectItem"):
        needs_restart = False
        for ps in item.spec["params"]:
            if item.fx["params"].get(ps["key"]) != ps["default"] and ps.get("restart"):
                needs_restart = True
            item.fx["params"][ps["key"]] = ps["default"]
            sl = item.sliders[ps["key"]]
            sl.value = ps["default"]; sl.update()
        if needs_restart:
            self.restart_effect(item)
        elif item.running:
            fxlib.set_controls(item.in_node.id, fxlib.controls(item.fx["type"], item.fx["params"]))
        self.cfg.save()

    def add_virtual(self):
        label, ok = QInputDialog.getText(self, "Virtual microphone",
                                         "Name (e.g. 'Discord Mix'):")
        if not ok or not label.strip():
            return
        label = label.strip()
        name = pw.slug(label)
        if any(v["name"] == name for v in self.cfg.virtual_mics):
            self.error(f"'{label}' already exists."); return
        try:
            pw.create_virtual_mic(label, name)
        except RuntimeError as e:
            self.error(str(e)); return
        self.cfg.virtual_mics.append({"name": name, "label": label})
        self.cfg.save()
        self.refresh(force=True)

    def rename_virtual(self, n: pw.Node):
        label, ok = QInputDialog.getText(self, "Rename", "New name:", text=n.label)
        if not ok or not label.strip():
            return
        # description is fixed at module load -> recreate, keep node.name (routes keep working)
        pw.remove_virtual_mic(n.name)
        try:
            pw.create_virtual_mic(label.strip(), n.name)
        except RuntimeError as e:
            self.error(str(e)); return
        for v in self.cfg.virtual_mics:
            if v["name"] == n.name:
                v["label"] = label.strip()
        self.cfg.save()
        self.refresh(force=True)

    def remove_virtual(self, n: pw.Node):
        if QMessageBox.question(self, "Delete", f"Delete '{n.label}'?") != QMessageBox.Yes:
            return
        pw.remove_virtual_mic(n.name)
        self.cfg.virtual_mics = [v for v in self.cfg.virtual_mics if v["name"] != n.name]
        self.cfg.routes = [r for r in self.cfg.routes if n.key not in r]
        self.cfg.blocked = [r for r in self.cfg.blocked if n.key not in r]
        self.cfg.forget(n.key)
        self.cfg.save()
        self.refresh(force=True)

    def forget_node(self, key: str):
        """Remove a greyed-out card. Saved routes are kept and apply again if the
        app/device comes back."""
        self.cfg.forget(key)
        self.cfg.save()
        self.refresh(force=True)

    def ignore_node(self, item: "NodeItem"):
        """Hide a node permanently. Connections/routes stay unchanged;
        undo via ⋯ → Hidden."""
        key = item.node.key
        self.cfg.ignored[key] = item.node.label or key
        self.cfg.forget(key)
        self.cfg.save()
        self.refresh(force=True)

    def unignore_node(self, key: str):
        self.cfg.ignored.pop(key, None)
        self.cfg.save()
        self.refresh(force=True)

    def reset_layout(self):
        self.cfg.order = {"left": [], "right": []}; self.cfg.save()
        for w in self.view.wires:
            w.detach(); self.view.scene_.removeItem(w)
        for it in list(self.view.node_items.values()):
            self.view.scene_.removeItem(it)
        self.view.node_items.clear(); self.view.wires.clear()
        self.refresh(force=True)

    # ---------------- theme
    def resolved_theme(self) -> str:
        if self.cfg.theme in ("dark", "light"):
            return self.cfg.theme
        scheme = QGuiApplication.styleHints().colorScheme()
        return "light" if scheme == Qt.ColorScheme.Light else "dark"

    def apply_theme(self):
        # application wide, so tooltips (separate windows) get the style too
        QApplication.instance().setStyleSheet(set_palette(self.resolved_theme()))
        self.view.setBackgroundBrush(COL["bg"])
        self.view.resetCachedContent()
        self.view.scene_.update()
        self.view.viewport().update()
        if hasattr(self, "header"):
            self.header.set_status(self.graph if self.graph.nodes else None,
                                   ignored=self.cfg.ignored)

    def set_theme(self, theme: str):
        self.cfg.theme = theme
        self.cfg.save()
        self.apply_theme()

    def show_about(self):
        QMessageBox.about(
            self, "About Node-Router",
            f"<b>Node-Router</b> {__version__}<br><br>"
            "PipeWire patchbay with virtual microphones and effect blocks.<br><br>"
            f'<a href="{REPO_URL}">{REPO_URL}</a><br><br>'
            "License: GPL-3.0-or-later – without any warranty.<br>"
            "Effects use PipeWire filter-chain, LSP Plugins and RNNoise "
            "(werman/noise-suppression-for-voice), bundled under their own licenses.")

    def open_config_dir(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG.parent)))

    def error(self, msg: str):
        QMessageBox.warning(self, "Node-Router", msg)


def main() -> int:
    if "--version" in sys.argv[1:]:
        print(f"Node-Router {__version__}")
        return 0
    paths.clean_host_env()                        # child processes: system environment
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    paths.icon_path()                             # bundled: store the icon permanently (desktop entries)
    paths.install_bundled_plugins()               # bundled: store plugins permanently (running effects)
    migrate_legacy_entries()                      # replace old "DIY Audio Router" entries
    minimized = "--minimized" in sys.argv[1:]
    app = QApplication(sys.argv)
    app.setApplicationName("Node-Router")
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(QIcon(str(ICON)))

    # single instance: if one is running, a second start only raises its
    # window (with --minimized from autostart: nothing at all) and exits.
    name = f"{APP_ID}-{os.getuid()}"
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(500):
        sock.write(b"noop" if minimized else b"show")
        sock.flush(); sock.waitForBytesWritten(500); sock.disconnectFromServer()
        print("Node-Router is already running.", file=sys.stderr)
        return 0
    QLocalServer.removeServer(name)               # orphaned socket after a crash
    server = QLocalServer()
    server.listen(name)

    tray = QSystemTrayIcon.isSystemTrayAvailable()
    app.setQuitOnLastWindowClosed(not tray)       # with tray: closing = background
    w = MainWindow(tray=tray, check_system=True)

    def on_connect():
        c = server.nextPendingConnection()
        def read():
            if bytes(c.readAll()).startswith(b"show"):
                w.show_window()
        c.readyRead.connect(read)
    server.newConnection.connect(on_connect)

    if not (minimized and tray):
        w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
