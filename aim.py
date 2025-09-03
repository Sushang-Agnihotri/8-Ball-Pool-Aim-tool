# aim.py
# Minimal, clean overlay with:
# - soft shadows sized to circle
# - double-bank lines
# - universal color
# - hotkeys 1–6 to send last-selected ball to a pocket
# - semi-lock (hysteresis) of bank/double-bank final endpoint (visual only)
# - NEW: Grab & Drop for p1/p2 (click once to pick up, move, click again to drop)
#
# Removed: Ghost ball, HUD, Auto-pocket, Click-through, per-color pickers.

import sys, os, json, math
from PyQt5 import QtCore, QtGui, QtWidgets

CONFIG_FILE = "pf_config.json"

def dist(a: QtCore.QPointF, b: QtCore.QPointF) -> float:
    return math.hypot(a.x() - b.x(), a.y() - b.y())

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
        self._w, self._h = 46, 26
        self.setFixedSize(self._w, self._h)
        self.toggled.connect(self._emit_now)
    def _emit_now(self, v): self.toggledImmediately.emit(v)
    def sizeHint(self): return QtCore.QSize(self._w, self._h)
    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        r = QtCore.QRectF(0, 0, self.width(), self.height()); radius = r.height()/2
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(76,217,100) if self.isChecked() else QtGui.QColor(204,204,204))
        p.drawRoundedRect(r, radius, radius)
        m = 2; d = r.height()-m*2; x = r.width()-m-d if self.isChecked() else m
        p.setBrush(QtGui.QColor("white")); p.drawEllipse(QtCore.QRectF(x,m,d,d))

class Overlay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        # Window
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setMouseTracking(True)

        # Table geometry
        self.table_rect = QtCore.QRectF(34, 171, 1133, 569)
        self.corner_radius = 22.0
        self.border_pen = QtGui.QPen(QtCore.Qt.white, 3, cap=QtCore.Qt.RoundCap, join=QtCore.Qt.RoundJoin)

        # Circles (bigger)
        self.pocket_radius = 14.0      # pocket ring & handle visual radius
        self.handle_radius = 12.0      # hit target for dragging p1/p2

        # Points
        self.p1 = QtCore.QPointF(self.table_rect.left() + self.table_rect.width()*0.25, self.table_rect.center().y())
        self.p2 = QtCore.QPointF(self.table_rect.right() - self.table_rect.width()*0.25, self.table_rect.center().y())
        self.marker = QtCore.QPointF(self.table_rect.center())
        self.last_target = 'p2'        # which ball the 1–6 hotkeys will move

        # State
        self.dragging_handle = None    # legacy press-and-hold drag
        self.locked = False

        # NEW: Grab & Drop state (click to pick, click to drop)
        self.carrying = None           # 'p1' or 'p2' while carrying, else None
        self.carry_offset = QtCore.QPointF(0, 0)  # keep relative offset at pick-up

        # Semi-lock state for bank/double-bank endpoint (visual only)
        self._snap_endpoint = None     # QPointF or None (current snapped pocket center)
        self._snap_active = False      # whether we are currently visually locked

        # Grips for table resize/move
        self.grip_size = 10
        self._build_grips()

        # Snapping
        self.snap_enabled = True
        self.snap_thresh = 24.0

        # Feature toggles
        self.show_lines_to_pockets = True
        self.show_single_aim_line = True
        self.show_bank_shot = True
        self.show_double_bank_shot = True

        # Visuals
        self.line_thickness = 3
        self.window_opacity = 0.95
        self.setWindowOpacity(self.window_opacity)

        # Universal color
        self.color_universal = QtGui.QColor(255, 255, 255)  # white by default

        # Menu button
        self.menu_button = QtWidgets.QPushButton("☰", self)
        self.menu_button.setFixedSize(44, 44)
        self.menu_button.setStyleSheet("border-radius:22px; background:white; color:black; border:1px solid black;")
        self.menu_button.move(40, 40)
        self.menu_button.clicked.connect(self._toggle_panel)

        # Panel
        self._build_panel()

        # Load config if present
        self.load_config()

        # Size
        self.resize(1200, 800)

    # ---------------- Panel -----------------
    def _build_panel(self):
        self.panel = QtWidgets.QFrame(self)
        self.panel.setFrameShape(QtWidgets.QFrame.Box)
        self.panel.setStyleSheet("background:white; color:black;")
        self.panel.setVisible(False)
        v = QtWidgets.QVBoxLayout(self.panel)
        v.setContentsMargins(10,10,10,10); v.setSpacing(8)

        v.addWidget(self._make_switch_row("6 hollow lines", True, lambda val: self._set_and_update('show_lines_to_pockets', val)))
        v.addWidget(self._make_switch_row("Single aim line", True, lambda val: self._set_and_update('show_single_aim_line', val)))
        v.addWidget(self._make_switch_row("Bank shot line", True, lambda val: self._set_and_update('show_bank_shot', val)))
        v.addWidget(self._make_switch_row("Double bank shot line", True, lambda val: self._set_and_update('show_double_bank_shot', val)))

        v.addLayout(self._make_slider_row("Line Thickness", 1, 10, self.line_thickness,
                                          lambda val: self._set_and_update('line_thickness', val)))
        v.addLayout(self._make_slider_row("Overlay Opacity", 30, 100, int(self.window_opacity*100),
                                          self._on_opacity_changed))

        btn = QtWidgets.QPushButton("Set Line Color (All)")
        btn.clicked.connect(self._pick_universal_color)
        v.addWidget(btn)

        row_sl = QtWidgets.QHBoxLayout()
        sbtn = QtWidgets.QPushButton("Save"); sbtn.clicked.connect(self.save_config)
        lbtn = QtWidgets.QPushButton("Load"); lbtn.clicked.connect(self.load_config)
        row_sl.addWidget(sbtn); row_sl.addWidget(lbtn); v.addLayout(row_sl)

        v.addWidget(QtWidgets.QLabel("Shortcuts: O menu • Enter lock/unlock • Esc close • 1–6 send ball to pocket"))

    def _make_switch_row(self, label, default, slot):
        cont = QtWidgets.QWidget(self.panel)
        h = QtWidgets.QHBoxLayout(cont); h.setContentsMargins(0,0,0,0)
        h.addWidget(QtWidgets.QLabel(label), 1)
        sw = IOSSwitch(checked=default); sw.toggledImmediately.connect(slot)
        h.addWidget(sw, 0, QtCore.Qt.AlignRight)
        return cont

    def _make_slider_row(self, label, lo, hi, val, slot):
        h = QtWidgets.QHBoxLayout()
        h.addWidget(QtWidgets.QLabel(label))
        s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        s.setRange(lo, hi); s.setValue(val); s.valueChanged.connect(slot)
        h.addWidget(s)
        return h

    def _set_and_update(self, name, value):
        setattr(self, name, value); self.update()

    def _pick_universal_color(self):
        col = QtWidgets.QColorDialog.getColor(self.color_universal, self, "Choose Line Color")
        if col.isValid():
            self.color_universal = col; self.update()

    def _on_opacity_changed(self, val: int):
        self.window_opacity = max(0.3, val / 100.0)
        self.setWindowOpacity(self.window_opacity); self.update()

    def _toggle_panel(self):
        if self.panel.isVisible(): self.panel.hide(); return
        self.panel.adjustSize()
        pw, ph = self.panel.sizeHint().width(), self.panel.sizeHint().height()
        b = self.menu_button.geometry()
        x = b.right()+8 if (b.right()+8+pw <= self.width()) else max(0, b.left()-8-pw)
        y = min(max(b.top(), 0), max(self.height()-ph, 0))
        self.panel.move(x, y); self.panel.raise_(); self.panel.show(); self.panel.activateWindow(); self.panel.setFocus()

    # ------------- Geometry helpers -------------
    def _build_grips(self):
        def TL_get(): return QtCore.QPointF(self.table_rect.left(), self.table_rect.top())
        def TM_get(): return QtCore.QPointF(self.table_rect.center().x(), self.table_rect.top())
        def TR_get(): return QtCore.QPointF(self.table_rect.right(), self.table_rect.top())
        def ML_get(): return QtCore.QPointF(self.table_rect.left(), self.table_rect.center().y())
        def MR_get(): return QtCore.QPointF(self.table_rect.right(), self.table_rect.center().y())
        def BL_get(): return QtCore.QPointF(self.table_rect.left(), self.table_rect.bottom())
        def BM_get(): return QtCore.QPointF(self.table_rect.center().x(), self.table_rect.bottom())
        def BR_get(): return QtCore.QPointF(self.table_rect.right(), self.table_rect.bottom())

        def TL_set(p): self._resize_from_points(p, anchor='BR')
        def TM_set(p): self._resize_edge_top(p)
        def TR_set(p): self._resize_from_points(p, anchor='BL')
        def ML_set(p): self._resize_edge_left(p)
        def MR_set(p): self._resize_edge_right(p)
        def BL_set(p): self._resize_from_points(p, anchor='TR')
        def BM_set(p): self._resize_edge_bottom(p)
        def BR_set(p): self._resize_from_points(p, anchor='TL')

        self.grips = [Grip(TL_get, TL_set), Grip(TM_get, TM_set), Grip(TR_get, TR_set),
                      Grip(ML_get, ML_set), Grip(MR_get, MR_set),
                      Grip(BL_get, BL_set), Grip(BM_get, BM_set), Grip(BR_get, BR_set)]

    def _normalize_rect(self):
        r = self.table_rect.normalized()
        if r.width() < 120: r.setWidth(120)
        if r.height() < 80: r.setHeight(80)
        self.table_rect = r

    def _clamp_to_window(self, p):
        x = min(max(p.x(), 0), self.width()); y = min(max(p.y(), 0), self.height())
        return QtCore.QPointF(x, y)

    def _keep_points_inside(self):
        def clamp_point(p):
            x = min(max(p.x(), self.table_rect.left()), self.table_rect.right())
            y = min(max(p.y(), self.table_rect.top()), self.table_rect.bottom())
            return QtCore.QPointF(x, y)
        self.p1 = clamp_point(self.p1); self.p2 = clamp_point(self.p2); self.marker = clamp_point(self.marker)

    def _resize_from_points(self, new_pos, anchor='TL'):
        r = QtCore.QRectF(self.table_rect); p = self._clamp_to_window(new_pos)
        if anchor == 'TL': r.setTopLeft(p)
        elif anchor == 'TR': r.setTopRight(p)
        elif anchor == 'BL': r.setBottomLeft(p)
        elif anchor == 'BR': r.setBottomRight(p)
        self.table_rect = r.normalized(); self._keep_points_inside(); self.update()

    def _resize_edge_left(self, p):
        p = self._clamp_to_window(p); r = QtCore.QRectF(self.table_rect); r.setLeft(p.x())
        self.table_rect = r.normalized(); self._keep_points_inside(); self.update()
    def _resize_edge_right(self, p):
        p = self._clamp_to_window(p); r = QtCore.QRectF(self.table_rect); r.setRight(p.x())
        self.table_rect = r.normalized(); self._keep_points_inside(); self.update()
    def _resize_edge_top(self, p):
        p = self._clamp_to_window(p); r = QtCore.QRectF(self.table_rect); r.setTop(p.y())
        self.table_rect = r.normalized(); self._keep_points_inside(); self.update()
    def _resize_edge_bottom(self, p):
        p = self._clamp_to_window(p); r = QtCore.QRectF(self.table_rect); r.setBottom(p.y())
        self.table_rect = r.normalized(); self._keep_points_inside(); self.update()

    # ------------- Pockets -------------
    def pocket_centers(self):
        r = self.table_rect
        return [
            QtCore.QPointF(r.left(), r.top()),
            QtCore.QPointF(r.center().x(), r.top()),
            QtCore.QPointF(r.right(), r.top()),
            QtCore.QPointF(r.left(), r.bottom()),
            QtCore.QPointF(r.center().x(), r.bottom()),
            QtCore.QPointF(r.right(), r.bottom()),
        ]

    def _maybe_snap(self, p: QtCore.QPointF) -> QtCore.QPointF:
        nearest, bestd = None, 1e9
        for c in self.pocket_centers():
            d = dist(p, c)
            if d < bestd: bestd, nearest = d, c
        return nearest if (nearest is not None and bestd <= self.snap_thresh) else p

    def _nearest_pocket_if_close(self, pt: QtCore.QPointF, radius_factor=1.2):
        # Returns (nearest_pocket_point, dist_to_it, base_snap_radius)
        snap_r = self.pocket_radius * radius_factor
        nearest, bestd = None, 1e9
        for c in self.pocket_centers():
            d = dist(pt, c)
            if d < bestd:
                bestd, nearest = d, c
        return (nearest, bestd, snap_r)

    def _clamp_point_to_table(self, p: QtCore.QPointF) -> QtCore.QPointF:
        x = min(max(p.x(), self.table_rect.left()), self.table_rect.right())
        y = min(max(p.y(), self.table_rect.top()), self.table_rect.bottom())
        return QtCore.QPointF(x, y)

    # ------------- Bank math -------------
    def _calculate_bank_shots(self, start_point, direction_x, direction_y, max_banks=2):
        segments = []
        current_pos = QtCore.QPointF(start_point)
        vx, vy = direction_x, direction_y
        for _ in range(max_banks):
            r = self.table_rect; tvals = []
            if vx > 0: tvals.append(((r.right()-current_pos.x())/vx, 'right'))
            elif vx < 0: tvals.append(((r.left()-current_pos.x())/vx, 'left'))
            if vy > 0: tvals.append(((r.bottom()-current_pos.y())/vy, 'bottom'))
            elif vy < 0: tvals.append(((r.top()-current_pos.y())/vy, 'top'))
            valid = [(t, side) for t,side in tvals if t and t > 0.001]
            if not valid: break
            t, side = min(valid, key=lambda x: x[0])
            hit = QtCore.QPointF(current_pos.x()+vx*t, current_pos.y()+vy*t)
            segments.append((QtCore.QPointF(current_pos), QtCore.QPointF(hit)))
            if side in ('left','right'): vx = -vx
            else: vy = -vy
            current_pos = hit
        return segments

    # ------------- Shadows (soft + sized to circle) -------------
    def _draw_shadow_line(self, painter: QtGui.QPainter, a: QtCore.QPointF, b: QtCore.QPointF):
        # Shadow thickness scales with circle size; keep it LIGHT (low alpha).
        outer = max(2, int(self.pocket_radius))
        inner = max(2, int(self.pocket_radius * 0.6))
        pen1 = QtGui.QPen(QtGui.QColor(self.color_universal.red(),
                                       self.color_universal.green(),
                                       self.color_universal.blue(), 30),
                          outer, cap=QtCore.Qt.RoundCap)
        pen2 = QtGui.QPen(QtGui.QColor(self.color_universal.red(),
                                       self.color_universal.green(),
                                       self.color_universal.blue(), 70),
                          inner, cap=QtCore.Qt.RoundCap)
        painter.setPen(pen1); painter.drawLine(a, b)
        painter.setPen(pen2); painter.drawLine(a, b)

    # ------------- Painting -------------
    def paintEvent(self, e: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self); painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # Table outline
        painter.setPen(self.border_pen); painter.setBrush(QtCore.Qt.NoBrush)
        path = QtGui.QPainterPath(); path.addRoundedRect(self.table_rect, self.corner_radius, self.corner_radius)
        painter.drawPath(path)

        # Pockets (hollow)
        painter.setPen(QtGui.QPen(self.color_universal, 1))
        for c in self.pocket_centers():
            painter.drawEllipse(c, self.pocket_radius, self.pocket_radius)

        # 6 hollow lines (marker → pockets) with soft shadow
        if self.show_lines_to_pockets:
            for c in self.pocket_centers(): self._draw_shadow_line(painter, self.marker, c)
            painter.setPen(QtGui.QPen(self.color_universal, self.line_thickness, cap=QtCore.Qt.RoundCap))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(self.marker, self.pocket_radius, self.pocket_radius)
            for c in self.pocket_centers(): painter.drawLine(self.marker, c)

        # Single aim line (p1 → p2) with shadow
        if self.show_single_aim_line:
            self._draw_shadow_line(painter, self.p1, self.p2)
            painter.setPen(QtGui.QPen(self.color_universal, self.line_thickness, cap=QtCore.Qt.RoundCap))
            painter.drawLine(self.p1, self.p2)

        # Bank & Double-bank lines with shadow + semi-lock endpoint
        dx = self.p2.x() - self.p1.x(); dy = self.p2.y() - self.p1.y()
        if (self.show_bank_shot or self.show_double_bank_shot) and (dx or dy):
            length = math.hypot(dx, dy); vx, vy = dx/length, dy/length
            max_banks = 4 if self.show_double_bank_shot else 2

            # First leg (p1 -> p2)
            self._draw_shadow_line(painter, self.p1, self.p2)
            painter.setPen(QtGui.QPen(self.color_universal, max(2, self.line_thickness+1), cap=QtCore.Qt.RoundCap))
            painter.drawLine(self.p1, self.p2)

            # Compute banks
            segments = self._calculate_bank_shots(self.p2, vx, vy, max_banks)

            # --- Semi-lock with hysteresis on FINAL endpoint ---
            base_snap_r = self.pocket_radius * 1.4   # stickier by default
            lock_r = base_snap_r                      # lock-in distance
            unlock_r = base_snap_r * 2.2              # release distance

            if segments:
                s_last, e_last = segments[-1]
                nearest, d_last, _ = self._nearest_pocket_if_close(e_last, radius_factor=lock_r / self.pocket_radius)

                # If we were snapped previously, keep it until far enough
                if self._snap_active and self._snap_endpoint is not None:
                    d_keep = dist(e_last, self._snap_endpoint)
                    if d_keep <= unlock_r:
                        # stay snapped
                        segments[-1] = (s_last, QtCore.QPointF(self._snap_endpoint))
                        nearest = self._snap_endpoint
                    else:
                        # release
                        self._snap_active = False
                        self._snap_endpoint = None
                        nearest = None

                # If not already snapped, try to lock in
                if not self._snap_active and nearest is not None and d_last <= lock_r:
                    self._snap_active = True
                    self._snap_endpoint = QtCore.QPointF(nearest)
                    segments[-1] = (s_last, QtCore.QPointF(self._snap_endpoint))

                # Draw a subtle highlight when snapped/near
                highlight = self._snap_endpoint if self._snap_active else (nearest if (nearest is not None and d_last <= lock_r) else None)
                if highlight is not None:
                    painter.setPen(QtGui.QPen(self.color_universal, 1))
                    painter.setBrush(QtCore.Qt.NoBrush)
                    painter.drawEllipse(highlight, self.pocket_radius + 3, self.pocket_radius + 3)

            # Render segments (shadow + line) once
            for s, e2 in segments:
                self._draw_shadow_line(painter, s, e2)
                painter.setPen(QtGui.QPen(self.color_universal, max(2, self.line_thickness+1), cap=QtCore.Qt.RoundCap))
                painter.drawLine(s, e2)

        # Handles (bigger, hollow)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(QtCore.Qt.white, 2))
        painter.drawEllipse(self.p1, self.pocket_radius, self.pocket_radius)
        painter.drawEllipse(self.p2, self.pocket_radius, self.pocket_radius)

        # Grips (only when unlocked)
        if not self.locked:
            painter.setBrush(QtCore.Qt.white); painter.setPen(QtCore.Qt.NoPen)
            for g in self.grips:
                gp = g.pos_getter()
                r = QtCore.QRectF(gp.x()-self.grip_size/2, gp.y()-self.grip_size/2, self.grip_size, self.grip_size)
                painter.drawRoundedRect(r, 2, 2)

    # ------------- Input -------------
    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if e.modifiers() & QtCore.Qt.ControlModifier and e.key() == QtCore.Qt.Key_S:
            self.save_config(); return
        if e.modifiers() & QtCore.Qt.ControlModifier and e.key() == QtCore.Qt.Key_L:
            self.load_config(); return

        k = e.key()
        if k == QtCore.Qt.Key_O: self._toggle_panel(); return
        if k == QtCore.Qt.Key_Escape:
            # cancel carry if active
            if self.carrying is not None:
                self.carrying = None
                self.update()
                return
            self.close(); return
        if k in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter): self.locked = not self.locked; self.update(); return

        # 1–6 hotkeys: send last-selected ball to that pocket
        key_to_index = {
            QtCore.Qt.Key_1: 0, QtCore.Qt.Key_2: 1, QtCore.Qt.Key_3: 2,
            QtCore.Qt.Key_4: 3, QtCore.Qt.Key_5: 4, QtCore.Qt.Key_6: 5
        }
        if k in key_to_index:
            idx = key_to_index[k]
            pockets = self.pocket_centers()
            if 0 <= idx < len(pockets):
                target = pockets[idx]
                if self.last_target == 'p1':
                    self.p1 = QtCore.QPointF(target)
                else:
                    self.p2 = QtCore.QPointF(target)
                self.update()
            return

        super().keyPressEvent(e)

    def _event_pos(self, e):
        return QtCore.QPointF(e.position() if hasattr(e, "position") else (e.localPos() if hasattr(e, "localPos") else e.pos()))

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        pos = self._event_pos(e)

        # If carrying, a left click drops the ball at current cursor
        if self.carrying is not None and e.button() == QtCore.Qt.LeftButton:
            # Drop at current mouse position (respect bounds and optional snap)
            pt = self._clamp_point_to_table(pos)
            if self.snap_enabled: pt = self._maybe_snap(pt)
            if self.carrying == 'p1': self.p1 = pt
            else: self.p2 = pt
            self.carrying = None
            self.update()
            return

        # If not carrying, a left click on p1/p2 picks it up (enter carry mode)
        if e.button() == QtCore.Qt.LeftButton:
            if dist(pos, self.p1) <= self.handle_radius:
                self.carrying = 'p1'
                self.last_target = 'p1'
                self.carry_offset = pos - self.p1
                self.update()
                return
            if dist(pos, self.p2) <= self.handle_radius:
                self.carrying = 'p2'
                self.last_target = 'p2'
                self.carry_offset = pos - self.p2
                self.update()
                return

        # Legacy press-and-hold drag (still available) — disabled while carrying
        if self.carrying is None:
            if dist(pos, self.marker) <= self.pocket_radius:
                self.dragging_handle = 'marker'; return
            if not self.locked:
                for i,g in enumerate(self.grips):
                    if dist(pos, g.pos_getter()) <= self.grip_size:
                        self.dragging_handle = ('grip', i); return
                if self.table_rect.contains(pos):
                    self.dragging_handle = ('table', pos - self.table_rect.topLeft()); return

        self.dragging_handle = None
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        pos = self._event_pos(e)

        # If carrying, move selected ball with the cursor (no mouse button held)
        if self.carrying is not None:
            p = pos - self.carry_offset
            p = self._clamp_point_to_table(p)
            if self.snap_enabled: p = self._maybe_snap(p)
            if self.carrying == 'p1': self.p1 = p
            else: self.p2 = p
            self.update()
            return

        # Legacy press-and-hold drag
        if self.dragging_handle == 'p1':
            self.p1 = self._clamp_point_to_table(pos)
            if self.snap_enabled: self.p1 = self._maybe_snap(self.p1)
            self.update(); return
        if self.dragging_handle == 'p2':
            self.p2 = self._clamp_point_to_table(pos)
            if self.snap_enabled: self.p2 = self._maybe_snap(self.p2)
            self.update(); return
        if self.dragging_handle == 'marker':
            self.marker = self._clamp_point_to_table(pos)
            self.update(); return
        if isinstance(self.dragging_handle, tuple):
            kind = self.dragging_handle[0]
            if kind == 'grip':
                idx = self.dragging_handle[1]; self.grips[idx].pos_setter(pos); self._normalize_rect(); self.update(); return
            if kind == 'table':
                offset = self.dragging_handle[1]
                new_tl = pos - offset
                dx = new_tl.x() - self.table_rect.left(); dy = new_tl.y() - self.table_rect.top()
                moved = QtCore.QRectF(self.table_rect); moved.translate(dx, dy)
                if moved.left() < 0: moved.translate(-moved.left(), 0)
                if moved.top() < 0: moved.translate(0, -moved.top())
                if moved.right() > self.width(): moved.translate(self.width()-moved.right(), 0)
                if moved.bottom() > self.height(): moved.translate(0, self.height()-moved.bottom())
                dp = QtCore.QPointF(moved.left()-self.table_rect.left(), moved.top()-self.table_rect.top())
                self.table_rect = moved; self.p1 += dp; self.p2 += dp; self.marker += dp
                self.update(); return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        # Grab & Drop uses click-to-drop, so mouseRelease doesn't commit anything
        self.dragging_handle = None
        super().mouseReleaseEvent(e)

    # ------------- Persist -------------
    def save_config(self):
        cfg = {
            "table_rect": [self.table_rect.left(), self.table_rect.top(), self.table_rect.width(), self.table_rect.height()],
            "p1": [self.p1.x(), self.p1.y()],
            "p2": [self.p2.x(), self.p2.y()],
            "marker": [self.marker.x(), self.marker.y()],
            "last_target": self.last_target,
            "toggles": {
                "lines": self.show_lines_to_pockets,
                "single": self.show_single_aim_line,
                "bank": self.show_bank_shot,
                "double_bank": self.show_double_bank_shot
            },
            "visuals": {"thickness": self.line_thickness, "opacity": self.window_opacity},
            "color": [self.color_universal.red(), self.color_universal.green(), self.color_universal.blue(), self.color_universal.alpha()]
        }
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=2)
            print("Config saved to", CONFIG_FILE)
        except Exception as ex:
            print("Save failed:", ex)

    def load_config(self):
        if not os.path.exists(CONFIG_FILE): return
        try:
            with open(CONFIG_FILE, "r") as f: cfg = json.load(f)
            tr = cfg.get("table_rect")
            if tr: self.table_rect = QtCore.QRectF(tr[0], tr[1], tr[2], tr[3])
            p1 = cfg.get("p1"); p2 = cfg.get("p2"); m = cfg.get("marker")
            if p1: self.p1 = QtCore.QPointF(p1[0], p1[1])
            if p2: self.p2 = QtCore.QPointF(p2[0], p2[1])
            if m: self.marker = QtCore.QPointF(m[0], m[1])
            self.last_target = cfg.get("last_target", self.last_target)
            tgl = cfg.get("toggles", {})
            self.show_lines_to_pockets = tgl.get("lines", self.show_lines_to_pockets)
            self.show_single_aim_line = tgl.get("single", self.show_single_aim_line)
            self.show_bank_shot = tgl.get("bank", self.show_bank_shot)
            self.show_double_bank_shot = tgl.get("double_bank", self.show_double_bank_shot)
            vis = cfg.get("visuals", {})
            self.line_thickness = vis.get("thickness", self.line_thickness)
            self.window_opacity = vis.get("opacity", self.window_opacity); self.setWindowOpacity(self.window_opacity)
            col = cfg.get("color")
            if col: self.color_universal = QtGui.QColor(*(col if len(col)==4 else col+[255]))
            print("Config loaded from", CONFIG_FILE); self.update()
        except Exception as ex:
            print("Load failed:", ex)

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = Overlay(); w.resize(1200, 800); w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
