"""Page de sortie : vue animée, panneau de données et profil du parcours."""

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QMessageBox,
                             QPushButton, QVBoxLayout, QWidget)

from .canvas import RideCanvas
from .theme import format_distance, format_duration, format_power, format_speed

World3DView = None
HAS_QTQUICK3D = False
try:
    from .world_view import HAS_QTQUICK3D, World3DView  # noqa: F401
except Exception:
    World3DView = None


def _fmt_value(value, suffix="--"):
    if value is None:
        return suffix
    return str(value)


class DataCard(QWidget):
    def __init__(self, title, unit=""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        title_label = QLabel(title)
        title_label.setStyleSheet("color:#8b95a7; font-size:12px;")
        self.value_label = QLabel("--")
        self.value_label.setObjectName("hud_value")
        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("hud_unit")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.unit_label)

    def set_value(self, value, unit=None):
        self.value_label.setText(value)
        if unit is not None:
            self.unit_label.setText(unit)


class ProfileWidget(QWidget):
    def __init__(self, route, parent=None):
        super().__init__(parent)
        self.route = route
        self.progress = 0.0
        self.setMinimumHeight(90)

    def set_progress(self, distance: float):
        self.progress = max(0.0, min(1.0, distance / max(1.0, self.route.length_m)))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#151c2a"))
        max_e = max(self.route.elevations) if self.route.elevations else 1.0
        min_e = min(self.route.elevations) if self.route.elevations else 0.0
        span = max(1.0, max_e - min_e)
        path = QPainterPath()
        path.moveTo(0, h)
        n = max(2, w // 3)
        for i in range(n):
            d = self.route.length_m * i / (n - 1)
            e = self.route.elevation_at(d)
            x = i / (n - 1) * w
            y = h - 6 - (e - min_e) / span * (h - 14)
            path.lineTo(x, y)
        path.lineTo(w, h)
        path.closeSubpath()
        p.setPen(QPen(Qt.PenStyle.NoPen))
        p.setBrush(QColor("#27354d"))
        p.drawPath(path)
        x = self.progress * w
        p.setPen(QPen(QColor("#ef6476"), 2))
        p.drawLine(QPointF(x, 0), QPointF(x, h))
        p.end()


class RidePage(QWidget):
    finished = pyqtSignal(dict)

    TICK_MS = 100

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        root = QVBoxLayout(self)
        content = QHBoxLayout()
        root.addLayout(content, 1)

        self.world = None
        self.world_view = None
        if World3DView is not None and HAS_QTQUICK3D:
            try:
                from ..world3d import build_world
                self.world = build_world(session.route)
                self.world_view = World3DView(self.world)
            except Exception:
                self.world_view = None
                self.world = None
        if self.world_view is not None:
            content.addWidget(self.world_view, 4)
            self.world_view.error_occurred.connect(self._fallback_2d)
            self.canvas = None
        else:
            self.canvas = RideCanvas(session.route.theme)
            content.addWidget(self.canvas, 4)

        side = QVBoxLayout()
        content.addLayout(side, 2)

        self.speed_card = DataCard("VITESSE", "km/h")
        self.power_card = DataCard("PUISSANCE", "watts")
        self.grade_card = DataCard("PENTE", "")
        self.distance_card = DataCard("DISTANCE", "")
        self.time_card = DataCard("TEMPS", "")
        self.hr_card = DataCard("CARDIO", "bpm")
        self.cadence_card = DataCard("CADENCE", "rpm")
        self.gain_card = DataCard("DÉNIVELÉ +", "mètres")

        for card in (self.speed_card, self.power_card, self.grade_card,
                     self.distance_card, self.time_card, self.hr_card,
                     self.cadence_card, self.gain_card):
            side.addWidget(card)

        self.quantity_label = QLabel("")
        self.quantity_label.setObjectName("subtitle")
        self.quantity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(self.quantity_label)

        self.info_label = QLabel("")
        self.info_label.setObjectName("subtitle")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        side.addWidget(self.info_label)

        side.addStretch(1)

        buttons_row = QHBoxLayout()
        self.pause_btn = QPushButton("Pause (Espace)")
        self.finish_btn = QPushButton("Terminer la séance")
        self.finish_btn.setObjectName("danger")
        buttons_row.addWidget(self.pause_btn)
        buttons_row.addWidget(self.finish_btn)
        side.addLayout(buttons_row)

        bottom = QVBoxLayout()
        self.profile = ProfileWidget(session.route)
        bottom.addWidget(self.profile)
        if session.trainer.is_simulated:
            bottom.addWidget(QLabel(
                "Démo : ↑ / ↓ ajustent l'effort — Espace : pause — Échap : terminer"))
        root.addLayout(bottom)

        self.pause_btn.clicked.connect(self._toggle_pause)
        self.finish_btn.clicked.connect(self._confirm_finish)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(self.TICK_MS)
        self._finished_emitted = False
        if self.world_view is not None:
            self.world_view.update_state(self.session.snapshot())

    def _fallback_2d(self, _message):
        if self.canvas is not None:
            return
        self.world_view.setParent(None)
        self.world_view.deleteLater()
        self.world_view = None
        self.world = None
        self.canvas = RideCanvas(self.session.route.theme)
        box = self.layout().itemAt(0).layout()
        box.insertWidget(0, self.canvas, 4)

    # --------------------------- interactions -----------------------------
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Up and self.session.trainer.is_simulated:
            self.session.effort_adjust(+8)
        elif key == Qt.Key.Key_Down and self.session.trainer.is_simulated:
            self.session.effort_adjust(-8)
        elif key == Qt.Key.Key_Space:
            self._toggle_pause()
        elif key == Qt.Key.Key_Escape:
            self._confirm_finish()
        else:
            super().keyPressEvent(event)

    def _toggle_pause(self):
        self.session.toggle_pause()
        self.pause_btn.setText("Reprendre (Espace)" if self.session.paused
                               else "Pause (Espace)")

    def _confirm_finish(self):
        box = QMessageBox(self)
        box.setWindowTitle("Terminer la séance")
        box.setText("Terminer la séance maintenant ?")
        box.setStandardButtons(QMessageBox.StandardButton.Yes |
                               QMessageBox.StandardButton.No)
        if box.exec() == QMessageBox.StandardButton.Yes:
            self._finish()

    def _finish(self):
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self.timer.stop()
        self.session.finished = True
        self.session.trainer.set_target_power(0)
        self.finished.emit(self.session.summary())

    # --------------------------- boucle ------------------------------------
    def tick(self):
        self.session.tick(self.TICK_MS / 1000.0)
        snap = self.session.snapshot()

        if self.world_view is not None:
            self.world_view.update_state(snap)
        else:
            self.canvas.update_state(snap)
        self.profile.set_progress(snap["distance"])

        self.speed_card.set_value(format_speed(snap["speed_kmh"]), "km/h")
        self.power_card.set_value(
            format_power(snap["power"]),
            f"moyenne {int(snap['avg_power'])} W")
        self.grade_card.set_value(f"{snap['grade_pct']:+.1f} %",
                                  f"{snap['elevation']:.0f} m d'altitude")
        self.distance_card.set_value(format_distance(snap["distance"]),
                                     f"restant {format_distance(snap['remaining'])}")
        self.time_card.set_value(format_duration(snap["elapsed"]),
                                 f"+{int(snap['elev_gain'])} m grimpés")
        self.hr_card.set_value(
            _fmt_value(int(snap["heart_rate"]) if snap["heart_rate"] else None),
            f"moyenne {int(snap['avg_hr'])} bpm" if snap["avg_hr"] else "bpm")
        self.cadence_card.set_value(
            _fmt_value(int(snap["cadence"]) if snap["cadence"] else None),
            f"moyenne {int(snap['avg_cadence'])} rpm" if snap["avg_cadence"] else "rpm")

        if self.session.workout:
            self._update_erg(snap)
        elif snap["route_done"]:
            self.info_label.setText("Parcours terminé, bravo !")
            self._finish()
        if self.session.finished and not self._finished_emitted:
            self._finish()

    def _update_erg(self, snap):
        seg = snap.get("segment")
        if seg is None:
            return
        target = snap["w_target"]
        self.quantity_label.setText(f"Cible : {target} W — {seg.label}")
        text = (f"Segment {snap['seg_index'] + 1}/{len(self.session.workout.segments)}"
                f" — {int(snap['seg_remaining'])} s restantes")
        actual = snap["power"]
        if abs(actual - target) > max(8.0, target * 0.12):
            text += f" — pédalez pour atteindre {target} W"
        self.info_label.setText(text)
