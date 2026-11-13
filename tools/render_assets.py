"""Render README screenshots and the demo GIF over a synthetic pool table.

Run from the repo root:  ``python tools/render_assets.py``  (needs PyQt5 and Pillow).
Nothing here touches the screen or any other process: frames are painted offscreen with
``Overlay.paint_scene`` onto a drawn background, so the images are reproducible.
"""

from __future__ import annotations

import io
import math
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["POOL_AIM_CONFIG"] = str(Path(tempfile.gettempdir()) / "pool-aim-render.json")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image  # noqa: E402
from PyQt5 import QtCore, QtGui, QtWidgets  # noqa: E402

from pool_aim.app import Overlay  # noqa: E402
from pool_aim.themes import THEMES  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "images"
W, H = 1280, 800
TABLE = QtCore.QRectF(150, 150, 980, 500)  # the overlay's "aim rectangle" (playing surface)


def draw_background(p: QtGui.QPainter, balls: list[tuple[QtCore.QPointF, QtGui.QColor, str]]):
    bg = QtGui.QLinearGradient(0, 0, 0, H)
    bg.setColorAt(0, QtGui.QColor(17, 22, 40))
    bg.setColorAt(1, QtGui.QColor(10, 13, 26))
    p.fillRect(0, 0, W, H, bg)
    # wooden rail
    rail = TABLE.adjusted(-46, -46, 46, 46)
    p.setPen(QtCore.Qt.NoPen)
    wood = QtGui.QLinearGradient(rail.topLeft(), rail.bottomRight())
    wood.setColorAt(0, QtGui.QColor(92, 54, 30))
    wood.setColorAt(1, QtGui.QColor(58, 32, 18))
    p.setBrush(wood)
    p.drawRoundedRect(rail, 34, 34)
    # cushion
    cush = TABLE.adjusted(-16, -16, 16, 16)
    p.setBrush(QtGui.QColor(18, 92, 84))
    p.drawRoundedRect(cush, 20, 20)
    # felt
    felt = QtGui.QRadialGradient(TABLE.center(), TABLE.width() * 0.6)
    felt.setColorAt(0, QtGui.QColor(34, 142, 126))
    felt.setColorAt(1, QtGui.QColor(14, 84, 76))
    p.setBrush(felt)
    p.drawRect(TABLE)
    # head string + spot
    p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 40), 1.5))
    x = TABLE.left() + TABLE.width() * 0.25
    p.drawLine(QtCore.QPointF(x, TABLE.top()), QtCore.QPointF(x, TABLE.bottom()))
    # pockets
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(QtGui.QColor(5, 5, 8))
    for cx, cy in [
        (TABLE.left(), TABLE.top()),
        (TABLE.center().x(), TABLE.top()),
        (TABLE.right(), TABLE.top()),
        (TABLE.left(), TABLE.bottom()),
        (TABLE.center().x(), TABLE.bottom()),
        (TABLE.right(), TABLE.bottom()),
    ]:
        p.drawEllipse(QtCore.QPointF(cx, cy), 26, 26)
    # diamonds
    p.setBrush(QtGui.QColor(230, 215, 170))
    for i in range(1, 8):
        for y in (TABLE.top() - 31, TABLE.bottom() + 31):
            p.drawEllipse(QtCore.QPointF(TABLE.left() + TABLE.width() * i / 8, y), 3.5, 3.5)
    for i in range(1, 4):
        for x in (TABLE.left() - 31, TABLE.right() + 31):
            p.drawEllipse(QtCore.QPointF(x, TABLE.top() + TABLE.height() * i / 4), 3.5, 3.5)
    # balls
    for pos, col, label in balls:
        r = 14.2
        p.setBrush(QtGui.QColor(0, 0, 0, 90))
        p.drawEllipse(pos + QtCore.QPointF(3, 4), r, r)
        g = QtGui.QRadialGradient(pos - QtCore.QPointF(4, 5), r * 1.6)
        g.setColorAt(0, col.lighter(160))
        g.setColorAt(1, col.darker(130))
        p.setBrush(g)
        p.drawEllipse(pos, r, r)
        if label:
            p.setBrush(QtGui.QColor(245, 245, 245))
            p.drawEllipse(pos, r * 0.5, r * 0.5)
            p.setPen(QtGui.QColor(20, 20, 20))
            f = QtGui.QFont("Arial", 7)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QtCore.QRectF(pos.x() - 8, pos.y() - 8, 16, 16), QtCore.Qt.AlignCenter, label)
            p.setPen(QtCore.Qt.NoPen)


def make_overlay(theme_idx=0, **flags) -> Overlay:
    w = Overlay(animate=True)
    w.resize(W, H)
    w.table_rect = QtCore.QRectF(TABLE)
    w.locked = True  # hide resize grips in screenshots
    w.marker = QtCore.QPointF(TABLE.center().x(), TABLE.center().y() + 120)
    w.set_theme(THEMES[theme_idx][1])
    for k, v in flags.items():
        w.set_flag(k, v)
    return w


def frame(w: Overlay, t: float = 0.8, toast: str | None = None, panel=False, scatter=True) -> QtGui.QImage:
    w._t0 = time.monotonic() - t
    w._toasts = [(toast, time.monotonic() - 0.4)] if toast else []
    img = QtGui.QImage(W, H, QtGui.QImage.Format_RGB32)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    balls = []
    if scatter:
        for pos, col, lab in [
            ((620, 250), (230, 190, 30), "1"),
            ((760, 560), (30, 70, 190), "2"),
            ((420, 610), (200, 40, 40), "3"),
            ((900, 230), (120, 40, 140), "4"),
            ((560, 520), (240, 120, 20), "5"),
        ]:
            balls.append((QtCore.QPointF(*pos), QtGui.QColor(*col), lab))
    balls.append((QtCore.QPointF(w.p2), QtGui.QColor(20, 20, 24), "8"))
    balls.append((QtCore.QPointF(w.p1), QtGui.QColor(245, 245, 240), ""))
    draw_background(p, balls)
    w.paint_scene(p)
    if panel:
        w._toggle_panel() if not w.panel.isVisible() else None
        w.panel.adjustSize()
        pix = w.panel.grab()
        p.drawPixmap(QtCore.QPoint(96, 40), pix)
    p.end()
    return img


def save(img: QtGui.QImage, name: str, width: int | None = None):
    if width:
        img = img.scaledToWidth(width, QtCore.Qt.SmoothTransformation)
    path = OUT / name
    img.save(str(path))
    print("wrote", path.relative_to(OUT.parent.parent), f"{path.stat().st_size // 1024} KB")


def to_pil(img: QtGui.QImage) -> Image.Image:
    buf = QtCore.QBuffer()
    buf.open(QtCore.QIODevice.ReadWrite)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    # 1. Hero: ghost ball + cut angle + bank
    w = make_overlay(2, lines=False, double_bank=False)
    w.p1 = QtCore.QPointF(300, 575)
    w.p2 = QtCore.QPointF(700, 330)
    save(frame(w, 0.9, toast="Locked 🔒"), "hero.png", 1280)

    # 2. Ghost ball
    w = make_overlay(1, bank=False, double_bank=False, lines=False)
    w.p1 = QtCore.QPointF(300, 560)
    w.p2 = QtCore.QPointF(640, 390)
    save(frame(w, 1.1), "ghost-ball.png", 900)

    # 3. Bank shot
    w = make_overlay(0, ghost=False, lines=False, double_bank=False)
    w.p1 = QtCore.QPointF(380, 520)
    w.p2 = QtCore.QPointF(500, 450)
    save(frame(w, 0.5), "bank-shot.png", 900)

    # 4. Double bank
    w = make_overlay(4, ghost=False, lines=False)
    w.p1 = QtCore.QPointF(300, 330)
    w.p2 = QtCore.QPointF(420, 290)
    save(frame(w, 0.6), "double-bank.png", 900)

    # 5. Pocket lines
    w = make_overlay(3, ghost=False, bank=False, double_bank=False, single=False)
    w.marker = QtCore.QPointF(700, 340)
    save(frame(w, 0.3), "pocket-lines.png", 900)

    # 6. Settings panel
    w = make_overlay(1)
    w.locked = False
    w.p1 = QtCore.QPointF(420, 540)
    w.p2 = QtCore.QPointF(640, 430)
    save(frame(w, 0.7, panel=True), "menu.png", 900)

    # 7. Help overlay
    w = make_overlay(2)
    w.show_help = True
    save(frame(w, 0.2), "help.png", 900)

    # 8. Themes grid
    tiles = []
    for i in range(len(THEMES)):
        w = make_overlay(i, lines=False, double_bank=False)
        w.p1 = QtCore.QPointF(360, 520)
        w.p2 = QtCore.QPointF(560, 440)
        f = frame(w, 0.7).scaledToWidth(560, QtCore.Qt.SmoothTransformation)
        p = QtGui.QPainter(f)
        p.setPen(QtGui.QColor(255, 255, 255))
        font = QtGui.QFont("Arial", 11)
        font.setBold(True)
        p.setFont(font)
        p.drawText(QtCore.QRectF(0, f.height() - 40, f.width(), 30), QtCore.Qt.AlignCenter, THEMES[i][0])
        p.end()
        tiles.append(f)
    cols, rows = 3, 2
    tw, th = tiles[0].width(), tiles[0].height()
    sheet = QtGui.QImage(tw * cols, th * rows, QtGui.QImage.Format_RGB32)
    p = QtGui.QPainter(sheet)
    for i, t in enumerate(tiles[:6]):
        p.drawImage((i % cols) * tw, (i // cols) * th, t)
    p.end()
    save(sheet, "themes.png")

    # 9. Animated demo GIF: object ball slides, aim sweeps, pulses flow
    w = make_overlay(2)
    w.set_flag("lines", False)
    frames = []
    n = 72
    for i in range(n):
        s = i / n
        w.p1 = QtCore.QPointF(300, 520)
        ang = math.sin(s * 2 * math.pi)
        w.p2 = QtCore.QPointF(520 + 70 * math.cos(s * 2 * math.pi), 420 + 90 * ang)
        w.carrying = "p2" if 0.0 <= s < 1 else None
        img = frame(w, t=i * 0.06, toast="Pick up · move · click to drop" if i < 30 else None)
        small = to_pil(img).resize((800, 500), Image.LANCZOS)
        frames.append(small.quantize(colors=128, method=Image.MEDIANCUT, dither=0))
    w.carrying = None
    frames[0].save(OUT / "demo.gif", save_all=True, append_images=frames[1:], duration=50, loop=0, optimize=True)
    print("wrote docs/images/demo.gif", (OUT / "demo.gif").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
