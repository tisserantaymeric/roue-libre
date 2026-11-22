"""Vue animée du parcours : ciel, relief, route, paysage défilant et cycliste."""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from ..routes import DEFAULT_THEME


def _qcolor(hexstr, alpha=255):
    c = QColor(hexstr)
    c.setAlpha(alpha)
    return c


def _hash01(n: float) -> float:
    x = math.sin(n * 127.1) * 43758.5453
    return x - math.floor(x)


class RideCanvas(QWidget):
    """Widget de dessin pur : reçoit un snapshot et se redessine."""

    def __init__(self, theme=None, parent=None):
        super().__init__(parent)
        self._snap = {}
        self._theme = dict(DEFAULT_THEME)
        if theme:
            self._theme.update(theme)
        self.setMinimumSize(400, 300)

    def update_state(self, snap: dict):
        self._snap = snap
        self.update()

    # --------------------------- panorama -------------------------------
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        snap = self._snap
        d = snap.get("distance", 0.0)
        grade = snap.get("grade_pct", 0.0) / 100.0
        horizon = int(h * 0.52)

        self._draw_sky(p, w, horizon, d)
        self._draw_far_hills(p, w, horizon, d, grade)
        p.fillRect(QRectF(0, horizon, w, h - horizon), _qcolor(self._theme["ground"]))
        self._draw_scenery(p, w, horizon, d)
        self._draw_road(p, w, h, horizon, d)
        self._draw_cyclist(p, w, h, snap)

        if snap.get("paused"):
            p.fillRect(self.rect(), _qcolor("#000000", 140))
            p.setPen(QPen(_qcolor("#ffffff")))
            font = QFont()
            font.setPixelSize(max(18, int(h / 22)))
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "En pause — Espace pour reprendre")
        p.end()

    def _draw_sky(self, p, w, horizon, d):
        grad = QLinearGradient(0, 0, 0, horizon)
        grad.setColorAt(0.0, _qcolor(self._theme["sky_top"]))
        grad.setColorAt(1.0, _qcolor(self._theme["sky_bottom"]))
        p.fillRect(QRectF(0, 0, w, horizon), grad)
        p.setBrush(_qcolor("#fff6d8", 220))
        p.setPen(QPen(Qt.PenStyle.NoPen))
        sun_x = w * 0.78
        sun_y = horizon * 0.25 + math.sin(d / 4000.0) * horizon * 0.05
        p.drawEllipse(QPointF(sun_x, sun_y), 28, 28)

    def _draw_far_hills(self, p, w, horizon, d, grade):
        layers = [
            ("hill_far", 0.030, horizon * 0.30),
            ("hill_near", 0.060, horizon * 0.18),
        ]
        for key, parallax, amplitude in layers:
            offset = d * parallax
            path = QPainterPath()
            path.moveTo(0, horizon)
            for x in range(0, w + 12, 12):
                t = (x + offset) * parallax * 7.0
                y = math.sin(t) * 0.6 + math.sin(t * 2.7) * 0.25 + math.cos(t * 0.6) * 0.25
                y_frac = 0.55 + 0.45 * (y + 0.5)
                if grade > 0.02:
                    climb = math.exp(-((x - w / 2) ** 2) / (2 * w * 0.25) ** 2)
                    y_frac -= climb * min(0.8, grade * 5.0) * 0.35
                path.lineTo(x, horizon - amplitude * y_frac)
            path.lineTo(w, horizon)
            path.closeSubpath()
            p.fillPath(path, _qcolor(self._theme[key]))

    # --------------------------- paysage ---------------------------------
    def _draw_scenery(self, p, w, horizon, d):
        kind = self._theme.get("scenery", "trees")
        base_y = horizon + (self.height() - horizon) * 0.25
        spacing = 90.0
        offset = d * 5.0
        j0 = math.floor(offset / spacing)
        count = int(w / spacing) + 3
        for j in range(j0 - 1, j0 + count):
            x = j * spacing - offset
            if j % 2 == 0:
                x += w * 0.55
            jitter = (_hash01(j) - 0.5) * spacing * 0.25
            px = x + jitter
            if px < -60 or px > w + 60:
                continue
            size = (0.55 + 0.9 * _hash01(j * 3 + 7)) * 26
            if kind == "pines":
                self._draw_pine(p, px, base_y, size)
            elif kind == "dunes":
                p.setPen(QPen(Qt.PenStyle.NoPen))
                p.setBrush(_qcolor(self._theme["hill_near"]))
                p.drawEllipse(QPointF(px, base_y), size * 1.6, size * 0.5)
            elif kind == "lake":
                p.setPen(QPen(Qt.PenStyle.NoPen))
                if j % 5 == 0:
                    p.setBrush(_qcolor("#4d7ea8", 200))
                    p.drawEllipse(QPointF(px, base_y + size * 0.3), size * 1.2, size * 0.35)
                else:
                    self._draw_tree(p, px, base_y, size * 0.8)
            else:
                self._draw_tree(p, px, base_y, size)

    def _draw_tree(self, p, x, base_y, size):
        p.setPen(QPen(Qt.PenStyle.NoPen))
        p.setBrush(QColor("#5d4632"))
        p.drawRect(QRectF(x - size * 0.07, base_y - size * 0.5, size * 0.14, size * 0.5))
        p.setBrush(QColor("#3f6b34"))
        p.drawEllipse(QPointF(x, base_y - size * 0.75), size * 0.45, size * 0.5)
        p.setBrush(QColor("#4a7d3c"))
        p.drawEllipse(QPointF(x - size * 0.18, base_y - size * 0.6), size * 0.3, size * 0.32)

    def _draw_pine(self, p, x, base_y, size):
        p.setPen(QPen(Qt.PenStyle.NoPen))
        p.setBrush(QColor("#5d4632"))
        p.drawRect(QRectF(x - size * 0.05, base_y - size * 0.3, size * 0.1, size * 0.3))
        p.setBrush(QColor("#2f5a3c"))
        for k, frac in enumerate((0.4, 0.7, 1.0)):
            top = base_y - size * (0.4 + 0.6 * frac)
            half = size * 0.45 * (1.0 - 0.25 * k)
            tri = QPolygonF([QPointF(x, top - size * 0.3),
                             QPointF(x - half, top),
                             QPointF(x + half, top)])
            p.drawPolygon(tri)

    # --------------------------- route -----------------------------------
    def _draw_road(self, p, w, h, horizon, d):
        vx = w / 2.0
        inset = w * 0.25
        bl = w * ((1.0 - 0.94) / 2.0)
        br = w * (1.0 - (1.0 - 0.94) / 2.0)
        p.setPen(QPen(Qt.PenStyle.NoPen))
        p.setBrush(_qcolor(self._theme["road"]))
        p.drawPolygon(QPolygonF([QPointF(vx - inset, horizon),
                                 QPointF(vx + inset, horizon),
                                 QPointF(br, h), QPointF(bl, h)]))
        p.setPen(QPen(QColor("#e8ecf3"), 2))
        p.drawLine(QPointF(vx - inset, horizon), QPointF(bl, h))
        p.drawLine(QPointF(vx + inset, horizon), QPointF(br, h))

        p.setPen(QPen(Qt.PenStyle.NoPen))
        p.setBrush(_qcolor("#d9dde6", 210))
        cycle = 8.0
        offset = d % cycle
        n_dashes = 16
        span = n_dashes * cycle
        for i in range(n_dashes):
            t0 = (i * cycle - offset) / span
            t1 = t0 + 4.0 / span
            if t1 <= 0 or t0 >= 1:
                continue
            t0 = max(0.0, t0)
            t1 = min(1.0, t1)
            y0 = horizon + (h - horizon) * (t0 ** 2)
            y1 = horizon + (h - horizon) * (t1 ** 2)
            road_width = (br - bl) * (t0 ** 2)
            dash_w = max(2.5, road_width * 0.012)
            p.drawRect(QRectF(w / 2 - dash_w / 2, y1, dash_w, max(1.0, y0 - y1)))

    # --------------------------- cycliste --------------------------------
    def _draw_cyclist(self, p, w, h, snap):
        cadence = snap.get("cadence") or 0.0
        elapsed = snap.get("elapsed", 0.0)
        crank = (elapsed * cadence / 60.0 * 2 * math.pi) if cadence > 1 else 0.0
        cx = w / 2.0
        base_y = h * 0.90
        s = min(w, h) / 420.0

        p.setPen(QPen(QColor("#1b1f27"), max(2.0, 3 * s)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        rear = QPointF(cx - 46 * s, base_y - 22 * s)
        front = QPointF(cx + 46 * s, base_y - 22 * s)
        p.drawEllipse(rear, 22 * s, 22 * s)
        p.drawEllipse(front, 22 * s, 22 * s)

        p.setPen(QPen(QColor(self._theme.get("accent", "#f5a623")), max(3.0, 4 * s)))
        p.drawLine(rear, QPointF(cx, base_y - 40 * s))
        p.drawLine(QPointF(cx, base_y - 40 * s), front)
        p.drawLine(rear, QPointF(cx - 8 * s, base_y - 52 * s))
        p.drawLine(QPointF(cx - 8 * s, base_y - 52 * s),
                   QPointF(front.x() - 6 * s, base_y - 46 * s))

        p.setPen(QPen(QColor("#e8ecf3"), max(3.0, 5 * s), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        shoulder = QPointF(cx - 4 * s, base_y - 78 * s)
        hip = QPointF(cx - 26 * s, base_y - 62 * s)
        p.drawLine(hip, shoulder)
        p.setBrush(QColor("#e8ecf3"))
        p.drawEllipse(shoulder, 7 * s, 7 * s)

        leg_len = 26 * s
        for phase in (0.0, math.pi):
            ang = crank + phase
            foot = QPointF(cx - 8 * s + math.cos(ang) * leg_len * 0.5,
                           base_y - 30 * s + math.sin(ang) * leg_len * 0.5)
            mid = QPointF((hip.x() + foot.x()) / 2 + 6 * s,
                          (hip.y() + foot.y()) / 2 - 6 * s)
            p.setPen(QPen(QColor("#c3cad6"), max(2.5, 3.5 * s), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(hip, mid)
            p.drawLine(mid, foot)

        p.setBrush(_qcolor("#000000", 70))
        p.setPen(QPen(Qt.PenStyle.NoPen))
        p.drawEllipse(QPointF(cx, base_y + 4 * s), 70 * s, 8 * s)
