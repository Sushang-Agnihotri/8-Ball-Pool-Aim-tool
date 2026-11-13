"""Qt overlay UI for Pool Aim.

A passive, transparent always-on-top overlay: it draws guides on screen and never
reads, injects into, or modifies any other process.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time

from PyQt5 import QtCore, QtGui, QtWidgets

from . import __version__, config, geometry
from .themes import THEMES, next_theme

log = logging.getLogger("pool_aim")

DEFAULT_FLAGS = {
    "lines": True,
    "single": True,
    "bank": True,
    "double_bank": True,
    "ghost": True,
    "hud": True,
    "animate": True,
    "snap": True,
}
FLAG_LABELS = [
    ("lines", "Pocket lines"),
    ("single", "Single aim line"),
    ("bank", "Bank shot"),
    ("double_bank", "Double bank shot"),
    ("ghost", "Ghost ball + cut angle"),
    ("hud", "Shot info HUD"),
    ("animate", "Animations"),
    ("snap", "Snap balls to pockets"),
]
SHORTCUTS = [
    ("Enter", "Lock / unlock the table"),
    ("Click ball", "Pick up, move, click again to drop"),
    ("1 - 6", "Send last-moved ball to a pocket"),
    ("X", "Swap cue and object ball"),
    ("G", "Toggle ghost ball + cut angle"),
    ("C", "Cycle colour theme"),
    ("A", "Toggle animations"),
    ("H", "Toggle shot info HUD"),
    ("O", "Open / close settings"),
    ("R", "Reset table and balls"),
    ("F11", "Cover the whole screen"),
    ("Ctrl+S / Ctrl+L", "Save / load settings"),
    ("F1  or  ?", "Show / hide this help"),
    ("Esc", "Cancel carry, then quit"),
]

PANEL_QSS = """
QFrame#panel { background: rgba(24,26,33,235); border: 1px solid rgba(255,255,255,40); border-radius: 14px; }
QLabel { color: #e8eaf0; font-size: 12px; }
QLabel#title { font-size: 15px; font-weight: 600; }
QLabel#muted { color: #8a90a2; font-size: 11px; }
QPushButton { background: rgba(255,255,255,18); color: #e8eaf0; border: 1px solid rgba(255,255,255,30);
              border-radius: 8px; padding: 6px 10px; }
QPushButton:hover { background: rgba(255,255,255,34); }
QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,40); border-radius: 2px; }
QSlider::handle:horizontal { background: #fff; width: 14px; margin: -6px 0; border-radius: 7px; }
QSlider::sub-page:horizontal { background: #4cd964; border-radius: 2px; }
"""


def dist(a: QtCore.QPointF, b: QtCore.QPointF) -> float:
    return math.hypot(a.x() - b.x(), a.y() - b.y())


def _pt(p: geometry.Point) -> QtCore.QPointF:
    return QtCore.QPointF(*p)


def _xy(p: QtCore.QPointF) -> geometry.Point:
    return (p.x(), p.y())


class Grip:
    def __init__(self, pos_getter, pos_setter):
        self.pos_getter = pos_getter
        self.pos_setter = pos_setter


class IOSSwitch(QtWidgets.QAbstractButton):
    toggledImmediately = QtCore.pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._w, self._h = 40, 22
        self.setFixedSize(self._w, self._h)
        self.toggled.connect(self.toggledImmediately.emit)

    def sizeHint(self):
        return QtCore.QSize(self._w, self._h)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        r = QtCore.QRectF(0, 0, self.width(), self.height())
        radius = r.height() / 2
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(76, 217, 100) if self.isChecked() else QtGui.QColor(90, 94, 108))
        p.drawRoundedRect(r, radius, radius)
        m = 2
        d = r.height() - m * 2
        x = r.width() - m - d if self.isChecked() else m
        p.setBrush(QtGui.QColor("white"))
        p.drawEllipse(QtCore.QRectF(x, m, d, d))


class Overlay(QtWidgets.QWidget):
    DEFAULT_TABLE = (34, 171, 1133, 569)

    def __init__(self, animate: bool | None = None):
        super().__init__()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setMouseTracking(True)
        self.setWindowTitle("Pool Aim")

        self.corner_radius = 22.0
        self.border_pen = QtGui.QPen(QtCore.Qt.white, 3, cap=QtCore.Qt.RoundCap, join=QtCore.Qt.RoundJoin)
        self.pocket_radius = 14.0
        self.handle_radius = 12.0
        self.grip_size = 10
        self.snap_thresh = 24.0

        self.flags = dict(DEFAULT_FLAGS)
        self.locked = False
        self.show_help = False
        self.line_thickness = 3
        self.window_opacity = 0.95
        self.color_universal = QtGui.QColor(255, 255, 255)
        self.setWindowOpacity(self.window_opacity)

        self.carrying = None
        self.carry_offset = QtCore.QPointF(0, 0)
        self.dragging_handle = None
        self._snap_endpoint = None
        self._snap_active = False
        self._fullscreen = False
        self._saved_geometry = None
        self._toasts: list[tuple[str, float]] = []
        self._t0 = time.monotonic()

        self.reset_layout()
        self._build_grips()

        self.menu_button = QtWidgets.QPushButton("☰", self)
        self.menu_button.setFixedSize(44, 44)
        self.menu_button.setToolTip("Settings (O)")
        self.menu_button.setStyleSheet(
            "QPushButton{border-radius:22px;background:rgba(24,26,33,235);color:white;"
            "border:1px solid rgba(255,255,255,90);font-size:18px;}"
            "QPushButton:hover{background:rgba(60,64,80,240);}"
        )
        self.menu_button.move(40, 40)
        self.menu_button.clicked.connect(self._toggle_panel)

        self.load_config()
        if animate is not None:
            self.flags["animate"] = animate
        self._build_panel()

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)
        self._sync_timer()
        self.resize(1200, 800)

    # ---------------- State helpers -----------------
    @property
    def t(self) -> float:
        """Seconds since start (drives all animations)."""
        return time.monotonic() - self._t0

    @property
    def ball_radius(self) -> float:
        return self.table_rect.width() * 0.0125

    def reset_layout(self):
        self.table_rect = QtCore.QRectF(*self.DEFAULT_TABLE)
        r = self.table_rect
        self.p1 = QtCore.QPointF(r.left() + r.width() * 0.25, r.center().y())
        self.p2 = QtCore.QPointF(r.right() - r.width() * 0.25, r.center().y())
        self.marker = QtCore.QPointF(r.center())
        self.last_target = "p2"
        self._snap_active = False
        self._snap_endpoint = None

    def _sync_timer(self):
        if not hasattr(self, "_timer"):
            return
        if self.flags["animate"]:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def toast(self, text: str):
        self._toasts.append((text, time.monotonic()))
        self._toasts = self._toasts[-3:]
        self.update()
        QtCore.QTimer.singleShot(2100, self.update)

    def set_flag(self, name: str, value: bool, notify: bool = False):
        self.flags[name] = value
        if name == "animate":
            self._sync_timer()
        if name in self._switches:
            sw = self._switches[name]
            if sw.isChecked() != value:
                sw.blockSignals(True)
                sw.setChecked(value)
                sw.blockSignals(False)
        if notify:
            label = dict(FLAG_LABELS)[name]
            self.toast(f"{label}: {'ON' if value else 'OFF'}")
        self.update()

    # ---------------- Panel -----------------
    def _build_panel(self):
        self._switches: dict[str, IOSSwitch] = {}
        self.panel = QtWidgets.QFrame(self)
        self.panel.setObjectName("panel")
        self.panel.setStyleSheet(PANEL_QSS)
        self.panel.setVisible(False)
        v = QtWidgets.QVBoxLayout(self.panel)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)

        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("🎱  Pool Aim")
        title.setObjectName("title")
        ver = QtWidgets.QLabel(f"v{__version__}")
        ver.setObjectName("muted")
        head.addWidget(title, 1)
        head.addWidget(ver)
        v.addLayout(head)

        for key, label in FLAG_LABELS:
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(label), 1)
            sw = IOSSwitch(checked=self.flags[key])
            sw.toggledImmediately.connect(lambda val, k=key: self.set_flag(k, val))
            self._switches[key] = sw
            row.addWidget(sw, 0, QtCore.Qt.AlignRight)
            v.addLayout(row)

        self._thick_slider = self._add_slider(v, "Line thickness", 1, 10, self.line_thickness, self._on_thickness)
        self._opac_slider = self._add_slider(
            v, "Overlay opacity", 30, 100, int(self.window_opacity * 100), self._on_opacity_changed
        )

        v.addWidget(QtWidgets.QLabel("Colour theme"))
        sw_row = QtWidgets.QHBoxLayout()
        sw_row.setSpacing(6)
        for name, rgb in THEMES:
            b = QtWidgets.QPushButton()
            b.setFixedSize(24, 24)
            b.setToolTip(name)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:rgb{rgb};border-radius:12px;"
                "border:2px solid rgba(255,255,255,120);padding:0;}}"
                "QPushButton:hover{border:2px solid white;}"
            )
            b.clicked.connect(lambda _=False, c=rgb, n=name: self.set_theme(c, n))
            sw_row.addWidget(b)
        custom = QtWidgets.QPushButton("…")
        custom.setFixedSize(24, 24)
        custom.setToolTip("Custom colour")
        custom.setStyleSheet("QPushButton{border-radius:12px;padding:0;}")
        custom.clicked.connect(self._pick_universal_color)
        sw_row.addWidget(custom)
        sw_row.addStretch(1)
        v.addLayout(sw_row)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(6)
        for i, (text, slot) in enumerate(
            [
                ("Swap balls (X)", self.swap_balls),
                ("Reset (R)", self.reset_all),
                ("Save", self.save_config),
                ("Load", self.load_config),
                ("Help (F1)", self.toggle_help),
                ("Fullscreen (F11)", self.toggle_fullscreen),
            ]
        ):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(slot)
            grid.addWidget(b, i // 2, i % 2)
        v.addLayout(grid)

        note = QtWidgets.QLabel("Passive overlay · no screen reading · no network")
        note.setObjectName("muted")
        v.addWidget(note)
        self.panel.setFixedWidth(300)

    def _add_slider(self, layout, label, lo, hi, val, slot):
        h = QtWidgets.QHBoxLayout()
        h.addWidget(QtWidgets.QLabel(label), 1)
        s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.setFixedWidth(140)
        s.valueChanged.connect(slot)
        h.addWidget(s)
        layout.addLayout(h)
        return s

    def _sync_panel(self):
        for key, sw in self._switches.items():
            sw.blockSignals(True)
            sw.setChecked(self.flags[key])
            sw.blockSignals(False)
        for slider, val in (
            (self._thick_slider, self.line_thickness),
            (self._opac_slider, int(self.window_opacity * 100)),
        ):
            slider.blockSignals(True)
            slider.setValue(val)
            slider.blockSignals(False)

    def _on_thickness(self, val: int):
        self.line_thickness = val
        self.update()

    def set_theme(self, rgb, name=""):
        self.color_universal = QtGui.QColor(*rgb)
        if name:
            self.toast(f"Theme: {name}")
        self.update()

    def cycle_theme(self):
        name, rgb = next_theme((self.color_universal.red(), self.color_universal.green(), self.color_universal.blue()))
        self.set_theme(rgb, name)

    def _pick_universal_color(self):
        col = QtWidgets.QColorDialog.getColor(self.color_universal, self, "Choose Line Color")
        if col.isValid():
            self.color_universal = col
            self.update()

    def _on_opacity_changed(self, val: int):
        self.window_opacity = max(0.3, val / 100.0)
        self.setWindowOpacity(self.window_opacity)
        self.update()

    def _toggle_panel(self):
        if self.panel.isVisible():
            self.panel.hide()
            return
        self.panel.adjustSize()
        pw, ph = self.panel.width(), self.panel.sizeHint().height()
        b = self.menu_button.geometry()
        x = b.right() + 8 if (b.right() + 8 + pw <= self.width()) else max(0, b.left() - 8 - pw)
        y = min(max(b.top(), 0), max(self.height() - ph, 0))
        self.panel.move(x, y)
        self.panel.raise_()
        self.panel.show()
        self.panel.activateWindow()
        self.panel.setFocus()

    # ---------------- Actions -----------------
    def swap_balls(self):
        self.p1, self.p2 = self.p2, self.p1
        self.last_target = "p1" if self.last_target == "p2" else "p2"
        self.toast("Swapped cue and object ball")

    def reset_all(self):
        self.reset_layout()
        self.toast("Reset table and balls")

    def toggle_help(self):
        self.show_help = not self.show_help
        self.update()

    def toggle_fullscreen(self):
        screen = self.screen() or QtWidgets.QApplication.primaryScreen()
        if not self._fullscreen:
            self._saved_geometry = self.geometry()
            self.setGeometry(screen.geometry())
        elif self._saved_geometry is not None:
            self.setGeometry(self._saved_geometry)
        self._fullscreen = not self._fullscreen
        self.toast("Covering screen" if self._fullscreen else "Windowed")

    def toggle_lock(self):
        self.locked = not self.locked
        self.toast("Locked 🔒" if self.locked else "Unlocked 🔓")

    # ------------- Geometry helpers -------------
    def _build_grips(self):
        r = lambda: self.table_rect  # noqa: E731
        spec = [
            (lambda: r().topLeft(), lambda p: self._resize_from_points(p, "BR")),
            (lambda: QtCore.QPointF(r().center().x(), r().top()), lambda p: self._resize_edge("top", p)),
            (lambda: r().topRight(), lambda p: self._resize_from_points(p, "BL")),
            (lambda: QtCore.QPointF(r().left(), r().center().y()), lambda p: self._resize_edge("left", p)),
            (lambda: QtCore.QPointF(r().right(), r().center().y()), lambda p: self._resize_edge("right", p)),
            (lambda: r().bottomLeft(), lambda p: self._resize_from_points(p, "TR")),
            (lambda: QtCore.QPointF(r().center().x(), r().bottom()), lambda p: self._resize_edge("bottom", p)),
            (lambda: r().bottomRight(), lambda p: self._resize_from_points(p, "TL")),
        ]
        self.grips = [Grip(g, s) for g, s in spec]

    def _normalize_rect(self):
        r = self.table_rect.normalized()
        if r.width() < 120:
            r.setWidth(120)
        if r.height() < 80:
            r.setHeight(80)
        self.table_rect = r

    def _clamp_to_window(self, p):
        return QtCore.QPointF(min(max(p.x(), 0), self.width()), min(max(p.y(), 0), self.height()))

    def _clamp_point_to_table(self, p: QtCore.QPointF) -> QtCore.QPointF:
        return _pt(geometry.clamp_to_rect(_xy(p), self._rect_tuple()))

    def _rect_tuple(self) -> geometry.Rect:
        r = self.table_rect
        return (r.left(), r.top(), r.right(), r.bottom())

    def _keep_points_inside(self):
        self.p1 = self._clamp_point_to_table(self.p1)
        self.p2 = self._clamp_point_to_table(self.p2)
        self.marker = self._clamp_point_to_table(self.marker)

    def _resize_from_points(self, new_pos, anchor="TL"):
        r = QtCore.QRectF(self.table_rect)
        p = self._clamp_to_window(new_pos)
        {"TL": r.setTopLeft, "TR": r.setTopRight, "BL": r.setBottomLeft, "BR": r.setBottomRight}[anchor](p)
        self.table_rect = r.normalized()
        self._keep_points_inside()
        self.update()

    def _resize_edge(self, edge, p):
        p = self._clamp_to_window(p)
        r = QtCore.QRectF(self.table_rect)
        {
            "left": lambda: r.setLeft(p.x()),
            "right": lambda: r.setRight(p.x()),
            "top": lambda: r.setTop(p.y()),
            "bottom": lambda: r.setBottom(p.y()),
        }[edge]()
        self.table_rect = r.normalized()
        self._keep_points_inside()
        self.update()

    # ------------- Pockets -------------
    def pocket_centers(self):
        return [_pt(c) for c in geometry.pocket_centers(self._rect_tuple())]

    def _maybe_snap(self, p: QtCore.QPointF) -> QtCore.QPointF:
        if not self.flags["snap"]:
            return p
        c, d = geometry.nearest_pocket(_xy(p), self._rect_tuple())
        return _pt(c) if d <= self.snap_thresh else p

    def _nearest_pocket_if_close(self, pt: QtCore.QPointF):
        c, d = geometry.nearest_pocket(_xy(pt), self._rect_tuple())
        return _pt(c), d

    # ------------- Bank math -------------
    def _calculate_bank_shots(self, start_point, direction_x, direction_y, max_banks=2):
        segs = geometry.bank_segments(_xy(start_point), (direction_x, direction_y), self._rect_tuple(), max_banks)
        return [(_pt(p), _pt(q)) for p, q in segs]

    # ------------- Painting helpers -------------
    def _rgba(self, alpha: int) -> QtGui.QColor:
        c = QtGui.QColor(self.color_universal)
        c.setAlpha(alpha)
        return c

    def _draw_shadow_line(self, painter: QtGui.QPainter, a: QtCore.QPointF, b: QtCore.QPointF):
        outer = max(2, int(self.pocket_radius))
        inner = max(2, int(self.pocket_radius * 0.6))
        painter.setPen(QtGui.QPen(self._rgba(30), outer, cap=QtCore.Qt.RoundCap))
        painter.drawLine(a, b)
        painter.setPen(QtGui.QPen(self._rgba(70), inner, cap=QtCore.Qt.RoundCap))
        painter.drawLine(a, b)

    def _draw_flow(self, painter, a, b, speed=60.0, alpha=230):
        """Animated light pulses travelling along a segment."""
        if not self.flags["animate"]:
            return
        pen = QtGui.QPen(
            QtGui.QColor(255, 255, 255, alpha), max(1.5, self.line_thickness * 0.6), cap=QtCore.Qt.RoundCap
        )
        pen.setDashPattern([0.1, 16.0])
        pen.setDashOffset(-self.t * speed / max(pen.widthF(), 1.0))
        painter.setPen(pen)
        painter.drawLine(a, b)

    def _pulse(self) -> float:
        return 0.5 + 0.5 * math.sin(self.t * 4.0) if self.flags["animate"] else 0.5

    def _ring(self, painter, c, radius, alpha=255, width=2, color=None):
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(color or QtGui.QColor(255, 255, 255, alpha), width))
        painter.drawEllipse(c, radius, radius)

    # ------------- Painting -------------
    def paintEvent(self, e: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self.paint_scene(painter)

    def paint_scene(self, painter: QtGui.QPainter):
        thick = self.line_thickness
        pen_main = QtGui.QPen(self.color_universal, thick, cap=QtCore.Qt.RoundCap)

        # Table outline
        painter.setPen(self.border_pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        path = QtGui.QPainterPath()
        path.addRoundedRect(self.table_rect, self.corner_radius, self.corner_radius)
        painter.drawPath(path)

        # Pockets
        painter.setPen(QtGui.QPen(self.color_universal, 1))
        for c in self.pocket_centers():
            painter.drawEllipse(c, self.pocket_radius, self.pocket_radius)

        # Pocket lines from marker
        if self.flags["lines"]:
            for c in self.pocket_centers():
                self._draw_shadow_line(painter, self.marker, c)
            painter.setPen(pen_main)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(self.marker, self.pocket_radius, self.pocket_radius)
            for c in self.pocket_centers():
                painter.drawLine(self.marker, c)

        # Single aim line
        if self.flags["single"]:
            self._draw_shadow_line(painter, self.p1, self.p2)
            painter.setPen(pen_main)
            painter.drawLine(self.p1, self.p2)

        # Bank / double bank
        segments = []
        dx, dy = self.p2.x() - self.p1.x(), self.p2.y() - self.p1.y()
        snapped = False
        if (self.flags["bank"] or self.flags["double_bank"]) and (dx or dy):
            length = math.hypot(dx, dy)
            vx, vy = dx / length, dy / length
            max_banks = 4 if self.flags["double_bank"] else 2
            bank_pen = QtGui.QPen(self.color_universal, max(2, thick + 1), cap=QtCore.Qt.RoundCap)

            self._draw_shadow_line(painter, self.p1, self.p2)
            painter.setPen(bank_pen)
            painter.drawLine(self.p1, self.p2)
            self._draw_flow(painter, self.p1, self.p2)

            segments = self._calculate_bank_shots(self.p2, vx, vy, max_banks)
            lock_r = self.pocket_radius * 1.4
            unlock_r = lock_r * 2.2

            if segments:
                s_last, e_last = segments[-1]
                nearest, d_last = self._nearest_pocket_if_close(e_last)
                if self._snap_active and self._snap_endpoint is not None:
                    if dist(e_last, self._snap_endpoint) <= unlock_r:
                        segments[-1] = (s_last, QtCore.QPointF(self._snap_endpoint))
                        nearest, d_last = self._snap_endpoint, 0.0
                    else:
                        self._snap_active = False
                        self._snap_endpoint = None
                if not self._snap_active and d_last <= lock_r:
                    self._snap_active = True
                    self._snap_endpoint = QtCore.QPointF(nearest)
                    segments[-1] = (s_last, QtCore.QPointF(self._snap_endpoint))
                snapped = self._snap_active and self._snap_endpoint is not None
                if snapped:
                    pr = self.pocket_radius + 3 + 5 * self._pulse()
                    self._ring(
                        painter, self._snap_endpoint, pr, color=self._rgba(int(120 + 130 * self._pulse())), width=2
                    )
                    self._ring(painter, self._snap_endpoint, self.pocket_radius + 2, color=self._rgba(255), width=1)

            for i, (s, e2) in enumerate(segments):
                self._draw_shadow_line(painter, s, e2)
                painter.setPen(bank_pen)
                painter.drawLine(s, e2)
                self._draw_flow(painter, s, e2, speed=60 + 10 * i)
                if i < len(segments) - 1:
                    # rail impact marker
                    painter.setBrush(self._rgba(200))
                    painter.setPen(QtCore.Qt.NoPen)
                    painter.drawEllipse(e2, 3.5, 3.5)

        # Ghost ball + cut angle
        info = None
        if self.flags["ghost"]:
            info = self._paint_ghost(painter, segments)

        # Handles
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(QtCore.Qt.white, 2))
        painter.drawEllipse(self.p1, self.pocket_radius, self.pocket_radius)
        painter.drawEllipse(self.p2, self.pocket_radius, self.pocket_radius)
        if self.carrying is not None:
            c = self.p1 if self.carrying == "p1" else self.p2
            self._ring(painter, c, self.pocket_radius + 4 + 4 * self._pulse(), color=self._rgba(210), width=2)
        # tiny labels so first-time users know which is which
        painter.setPen(QtGui.QColor(255, 255, 255, 230))
        small = QtGui.QFont(self.font())
        small.setPointSizeF(8.0)
        small.setBold(True)
        painter.setFont(small)
        painter.drawText(QtCore.QRectF(self.p1.x() - 12, self.p1.y() - 12, 24, 24), QtCore.Qt.AlignCenter, "C")
        painter.drawText(QtCore.QRectF(self.p2.x() - 12, self.p2.y() - 12, 24, 24), QtCore.Qt.AlignCenter, "8")

        # Grips
        if not self.locked:
            painter.setBrush(QtCore.Qt.white)
            painter.setPen(QtCore.Qt.NoPen)
            for g in self.grips:
                gp = g.pos_getter()
                painter.drawRoundedRect(
                    QtCore.QRectF(
                        gp.x() - self.grip_size / 2, gp.y() - self.grip_size / 2, self.grip_size, self.grip_size
                    ),
                    2,
                    2,
                )

        if self.flags["hud"]:
            self._paint_hud(painter, info, segments, snapped)
        self._paint_toasts(painter)
        if self.show_help:
            self._paint_help(painter)

    def _paint_ghost(self, painter, segments):
        rect = self._rect_tuple()
        cue, obj = _xy(self.p1), _xy(self.p2)
        if geometry.dist(cue, obj) < 1:
            return None
        best = geometry.best_pocket(cue, obj, rect, self.ball_radius)
        if best is None:
            return None
        idx, angle = best
        pocket = geometry.pocket_centers(rect)[idx]
        ghost = geometry.ghost_ball(obj, pocket, self.ball_radius)

        # object ball -> pocket guide
        pen = QtGui.QPen(self._rgba(220), max(1.5, self.line_thickness * 0.7), QtCore.Qt.DashLine, QtCore.Qt.RoundCap)
        if self.flags["animate"]:
            pen.setDashOffset(-self.t * 3)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawLine(_pt(obj), _pt(pocket))
        # cue -> ghost
        painter.setPen(QtGui.QPen(self._rgba(120), 1.5, QtCore.Qt.DotLine))
        painter.drawLine(_pt(cue), _pt(ghost))
        # ghost ball
        painter.setBrush(self._rgba(40))
        painter.setPen(QtGui.QPen(self._rgba(255), 1.8, QtCore.Qt.DotLine))
        painter.drawEllipse(_pt(ghost), self.ball_radius, self.ball_radius)
        # target pocket highlight
        self._ring(painter, _pt(pocket), self.pocket_radius + 4 + 3 * self._pulse(), color=self._rgba(190), width=2)
        # angle label near object ball
        label = f"{angle:.0f}°"
        font = QtGui.QFont(self.font())
        font.setPointSizeF(10.0)
        font.setBold(True)
        painter.setFont(font)
        fm = QtGui.QFontMetricsF(font)
        w = fm.horizontalAdvance(label) + 14
        box = QtCore.QRectF(obj[0] + self.ball_radius + 6, obj[1] - 30, w, 20)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(15, 17, 23, 215))
        painter.drawRoundedRect(box, 10, 10)
        painter.setPen(self._rgba(255))
        painter.drawText(box, QtCore.Qt.AlignCenter, label)
        length = geometry.dist(cue, obj) + geometry.dist(obj, pocket)
        return {"pocket": idx + 1, "angle": angle, "length": length}

    def _pill(self, painter, rect, text, alpha=215, accent=False):
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(15, 17, 23, alpha))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        if accent:
            painter.setPen(QtGui.QPen(self._rgba(160), 1))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setPen(QtGui.QColor(240, 242, 248))
        painter.drawText(rect, QtCore.Qt.AlignCenter, text)

    def _paint_hud(self, painter, info, segments, snapped):
        font = QtGui.QFont(self.font())
        font.setPointSizeF(9.5)
        painter.setFont(font)
        parts = ["🔒 Locked" if self.locked else "🔓 Unlocked"]
        if info:
            diff = geometry.difficulty(info["angle"], info["length"], self.table_rect.width())
            parts.append(f"Cut {info['angle']:.0f}° → pocket {info['pocket']}")
            parts.append(diff)
        if segments:
            parts.append(f"{max(0, len(segments) - 1)} bank{'s' if len(segments) != 2 else ''}")
            if snapped:
                parts.append("pocketed ✔")
        text = "   ·   ".join(parts)
        fm = QtGui.QFontMetricsF(font)
        w = fm.horizontalAdvance(text) + 36
        rect = QtCore.QRectF((self.width() - w) / 2, 12, w, 28)
        self._pill(painter, rect, text, accent=True)

    def _paint_toasts(self, painter):
        now = time.monotonic()
        self._toasts = [(t, b) for t, b in self._toasts if now - b < 2.0]
        font = QtGui.QFont(self.font())
        font.setPointSizeF(10.0)
        painter.setFont(font)
        fm = QtGui.QFontMetricsF(font)
        for i, (text, born) in enumerate(reversed(self._toasts)):
            age = now - born
            a = 1.0 if age < 1.4 else max(0.0, 1 - (age - 1.4) / 0.6)
            rise = min(age / 0.2, 1.0)
            w = fm.horizontalAdvance(text) + 34
            y = self.height() - 56 - i * 36 + (1 - rise) * 12
            painter.setOpacity(a)
            self._pill(painter, QtCore.QRectF((self.width() - w) / 2, y, w, 28), text, alpha=235, accent=True)
        painter.setOpacity(1.0)

    def _paint_help(self, painter):
        w, h = 440.0, 60.0 + 26.0 * len(SHORTCUTS)
        box = QtCore.QRectF((self.width() - w) / 2, max(60.0, (self.height() - h) / 2), w, h)
        painter.setPen(QtGui.QPen(self._rgba(120), 1))
        painter.setBrush(QtGui.QColor(18, 20, 27, 240))
        painter.drawRoundedRect(box, 16, 16)
        title = QtGui.QFont(self.font())
        title.setPointSizeF(13.0)
        title.setBold(True)
        painter.setFont(title)
        painter.setPen(QtGui.QColor(255, 255, 255))
        painter.drawText(
            QtCore.QRectF(box.left() + 20, box.top() + 10, w - 40, 30), QtCore.Qt.AlignVCenter, "Pool Aim — shortcuts"
        )
        body = QtGui.QFont(self.font())
        body.setPointSizeF(10.0)
        painter.setFont(body)
        for i, (key, desc) in enumerate(SHORTCUTS):
            y = box.top() + 48 + i * 26
            painter.setPen(self._rgba(255))
            painter.drawText(QtCore.QRectF(box.left() + 20, y, 140, 22), QtCore.Qt.AlignVCenter, key)
            painter.setPen(QtGui.QColor(215, 218, 228))
            painter.drawText(QtCore.QRectF(box.left() + 170, y, w - 190, 22), QtCore.Qt.AlignVCenter, desc)

    # ------------- Input -------------
    def keyPressEvent(self, e: QtGui.QKeyEvent):
        k = e.key()
        ctrl = e.modifiers() & QtCore.Qt.ControlModifier
        if ctrl and k == QtCore.Qt.Key_S:
            self.save_config()
            return
        if ctrl and k == QtCore.Qt.Key_L:
            self.load_config()
            return
        simple = {
            QtCore.Qt.Key_O: self._toggle_panel,
            QtCore.Qt.Key_X: self.swap_balls,
            QtCore.Qt.Key_R: self.reset_all,
            QtCore.Qt.Key_C: self.cycle_theme,
            QtCore.Qt.Key_F1: self.toggle_help,
            QtCore.Qt.Key_Question: self.toggle_help,
            QtCore.Qt.Key_F11: self.toggle_fullscreen,
            QtCore.Qt.Key_Return: self.toggle_lock,
            QtCore.Qt.Key_Enter: self.toggle_lock,
            QtCore.Qt.Key_G: lambda: self.set_flag("ghost", not self.flags["ghost"], notify=True),
            QtCore.Qt.Key_H: lambda: self.set_flag("hud", not self.flags["hud"], notify=True),
            QtCore.Qt.Key_A: lambda: self.set_flag("animate", not self.flags["animate"], notify=True),
        }
        if k in simple and not ctrl:
            simple[k]()
            return
        if k == QtCore.Qt.Key_Escape:
            if self.show_help:
                self.toggle_help()
            elif self.carrying is not None:
                self.carrying = None
                self.update()
            else:
                self.close()
            return

        if QtCore.Qt.Key_1 <= k <= QtCore.Qt.Key_6:
            target = self.pocket_centers()[k - QtCore.Qt.Key_1]
            if self.last_target == "p1":
                self.p1 = QtCore.QPointF(target)
            else:
                self.p2 = QtCore.QPointF(target)
            self.update()
            return
        super().keyPressEvent(e)

    def _event_pos(self, e):
        return QtCore.QPointF(
            e.position() if hasattr(e, "position") else (e.localPos() if hasattr(e, "localPos") else e.pos())
        )

    def _place(self, which: str, pt: QtCore.QPointF):
        pt = self._maybe_snap(self._clamp_point_to_table(pt))
        if which == "p1":
            self.p1 = pt
        else:
            self.p2 = pt

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        pos = self._event_pos(e)
        left = e.button() == QtCore.Qt.LeftButton

        if self.carrying is not None and left:
            self._place(self.carrying, pos)
            self.carrying = None
            self.update()
            return

        if left:
            for name in ("p1", "p2"):
                if dist(pos, getattr(self, name)) <= self.handle_radius:
                    self.carrying = name
                    self.last_target = name
                    self.carry_offset = pos - getattr(self, name)
                    self.update()
                    return

        if self.carrying is None:
            if dist(pos, self.marker) <= self.pocket_radius:
                self.dragging_handle = "marker"
                return
            if not self.locked:
                for i, g in enumerate(self.grips):
                    if dist(pos, g.pos_getter()) <= self.grip_size:
                        self.dragging_handle = ("grip", i)
                        return
                if self.table_rect.contains(pos):
                    self.dragging_handle = ("table", pos - self.table_rect.topLeft())
                    return

        self.dragging_handle = None
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        pos = self._event_pos(e)

        if self.carrying is not None:
            self._place(self.carrying, pos - self.carry_offset)
            self.update()
            return

        if self.dragging_handle == "marker":
            self.marker = self._clamp_point_to_table(pos)
            self.update()
            return
        if isinstance(self.dragging_handle, tuple):
            kind, arg = self.dragging_handle
            if kind == "grip":
                self.grips[arg].pos_setter(pos)
                self._normalize_rect()
                self.update()
                return
            if kind == "table":
                moved = QtCore.QRectF(self.table_rect)
                new_tl = pos - arg
                moved.translate(new_tl.x() - moved.left(), new_tl.y() - moved.top())
                if moved.left() < 0:
                    moved.translate(-moved.left(), 0)
                if moved.top() < 0:
                    moved.translate(0, -moved.top())
                if moved.right() > self.width():
                    moved.translate(self.width() - moved.right(), 0)
                if moved.bottom() > self.height():
                    moved.translate(0, self.height() - moved.bottom())
                dp = QtCore.QPointF(moved.left() - self.table_rect.left(), moved.top() - self.table_rect.top())
                self.table_rect = moved
                self.p1 += dp
                self.p2 += dp
                self.marker += dp
                self.update()
                return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        self.dragging_handle = None
        super().mouseReleaseEvent(e)

    # ------------- Persist -------------
    def save_config(self):
        r = self.table_rect
        cfg = {
            "table_rect": [r.left(), r.top(), r.width(), r.height()],
            "p1": [self.p1.x(), self.p1.y()],
            "p2": [self.p2.x(), self.p2.y()],
            "marker": [self.marker.x(), self.marker.y()],
            "last_target": self.last_target,
            "toggles": dict(self.flags),
            "visuals": {"thickness": self.line_thickness, "opacity": self.window_opacity},
            "color": [
                self.color_universal.red(),
                self.color_universal.green(),
                self.color_universal.blue(),
                self.color_universal.alpha(),
            ],
        }
        try:
            log.info("Config saved to %s", config.save(cfg))
            self.toast("Settings saved ✔")
        except OSError as ex:
            log.error("Save failed: %s", ex)
            self.toast("Could not save settings")

    def load_config(self):
        cfg = config.load()
        if not cfg:
            return
        if "table_rect" in cfg:
            self.table_rect = QtCore.QRectF(*cfg["table_rect"])
        for name in ("p1", "p2", "marker"):
            if name in cfg:
                setattr(self, name, QtCore.QPointF(*cfg[name]))
        self.last_target = cfg.get("last_target", self.last_target)
        for k, v in cfg.get("toggles", {}).items():
            self.flags[k] = v
        vis = cfg.get("visuals", {})
        self.line_thickness = vis.get("thickness", self.line_thickness)
        self.window_opacity = vis.get("opacity", self.window_opacity)
        self.setWindowOpacity(self.window_opacity)
        if "color" in cfg:
            self.color_universal = QtGui.QColor(*cfg["color"])
        self._keep_points_inside()
        if hasattr(self, "_switches"):
            self._sync_panel()
            self._sync_timer()
            self.toast("Settings loaded ✔")
        log.info("Config loaded")
        self.update()


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="pool-aim", description="Passive on-screen aiming overlay for pool/billiards.")
    ap.add_argument("--version", action="version", version=f"pool-aim {__version__}")
    ap.add_argument("--no-animation", action="store_true", help="start with animations disabled")
    ap.add_argument("--fullscreen", action="store_true", help="start with the overlay covering the whole screen")
    ap.add_argument("--reset-config", action="store_true", help="ignore the saved settings file for this run")
    return ap.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if args.reset_config:
        import os
        import tempfile

        os.environ["POOL_AIM_CONFIG"] = os.path.join(tempfile.mkdtemp(prefix="pool-aim-"), "config.json")
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    app = QtWidgets.QApplication(sys.argv[:1])
    w = Overlay(animate=False if args.no_animation else None)
    w.show()
    if args.fullscreen:
        w.toggle_fullscreen()
    w.toast("Press F1 for help")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
