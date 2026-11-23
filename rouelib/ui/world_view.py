"""Intégration Qt Quick 3D : vue 3D du monde et pont vers le snapshot.

Si Qt Quick 3D n'est pas disponible (paquet PyQt6-3D absent ou pas d'OpenGL),
l'interface retombe sur la vue 2D existante — voir ride_screen.py.
"""

import math
import time
from pathlib import Path

from PyQt6.QtCore import (QObject, QUrl, QT_VERSION_STR, pyqtProperty,
                          pyqtSignal, pyqtSlot)
from PyQt6.QtQuickWidgets import QQuickWidget

from ..rider import advance_crank, leg_pose

try:
    import PyQt6.QtQuick3D  # noqa: F401 — enregistre les types Quick3D
    HAS_QTQUICK3D = True
except Exception:
    HAS_QTQUICK3D = False

QML_PATH = Path(__file__).resolve().parent.parent / "assets" / "qml" / "WorldView.qml"

CAM_BACK = 5.0
CAM_UP = 2.2
CAM_AHEAD = 10.0


class WorldBridge(QObject):
    """Expose l'état de la sortie aux liaisons QML (apté aux mises à jour)."""

    viewUpdated = pyqtSignal()
    terrainError = pyqtSignal(str)

    def __init__(self, theme: dict, terrain_url: str, texture_url: str,
                 jersey_color: str, bike_color: str):
        super().__init__()
        self._crank = 0.0
        self._last_tick = time.monotonic()
        legs = leg_pose(0.0)
        legs_b = leg_pose(0.0, 180.0)
        self._d = {
            "sky": theme.get("sky_top", "#1b2a4a"),
            "frame": theme.get("accent", "#f5a623"),
            "terrain_url": terrain_url,
            "texture_url": texture_url,
            "jersey": jersey_color,
            "bike": bike_color,
            "px": 0.0, "py": 0.0, "pz": 0.0, "yaw": 0.0, "pitch": 0.0,
            "cx": 0.0, "cy": 0.0, "cz": 0.0, "camYaw": 0.0, "camPitch": 0.0,
            "cadence": 0.0,
            "crank": 0.0,
            "thighZ0": legs["thigh_z"], "kneeZ0": legs["knee_z"],
            "thighZ1": legs_b["thigh_z"], "kneeZ1": legs_b["knee_z"],
        }

    def update(self, snap: dict, pose: dict, cam: dict):
        now = time.monotonic()
        dt = min(now - self._last_tick, 0.5)
        self._last_tick = now
        cadence = float(snap.get("cadence") or 0.0)
        self._crank = advance_crank(self._crank, cadence, dt)
        legs_a = leg_pose(self._crank, 0.0)
        legs_b = leg_pose(self._crank, 180.0)
        self._d.update({
            "px": pose["x"], "py": pose["y"] + 0.02, "pz": pose["z"],
            "yaw": pose["yaw_deg"], "pitch": pose["pitch_deg"],
            "cx": cam["x"], "cy": cam["y"], "cz": cam["z"],
            "camYaw": cam["yaw_deg"], "camPitch": cam["pitch_deg"],
            "cadence": cadence,
            "crank": self._crank,
            "thighZ0": legs_a["thigh_z"], "kneeZ0": legs_a["knee_z"],
            "thighZ1": legs_b["thigh_z"], "kneeZ1": legs_b["knee_z"],
        })
        self.viewUpdated.emit()

    @pyqtProperty(str, notify=viewUpdated)
    def skyColor(self):
        return self._d["sky"]

    @pyqtProperty(str, notify=viewUpdated)
    def frameColor(self):
        return self._d["frame"]

    @pyqtProperty(str, notify=viewUpdated)
    def terrainUrl(self):
        return self._d["terrain_url"]

    @pyqtProperty(str, notify=viewUpdated)
    def textureUrl(self):
        return self._d["texture_url"]

    @pyqtProperty(str, notify=viewUpdated)
    def jerseyColor(self):
        return self._d["jersey"]

    @pyqtProperty(str, notify=viewUpdated)
    def bikeColor(self):
        return self._d["bike"]

    @pyqtProperty(float, notify=viewUpdated)
    def crank(self):
        return self._d["crank"]

    @pyqtProperty(float, notify=viewUpdated)
    def thighZ0(self):
        return self._d["thighZ0"]

    @pyqtProperty(float, notify=viewUpdated)
    def kneeZ0(self):
        return self._d["kneeZ0"]

    @pyqtProperty(float, notify=viewUpdated)
    def thighZ1(self):
        return self._d["thighZ1"]

    @pyqtProperty(float, notify=viewUpdated)
    def kneeZ1(self):
        return self._d["kneeZ1"]

    @pyqtProperty(float, notify=viewUpdated)
    def px(self):
        return self._d["px"]

    @pyqtProperty(float, notify=viewUpdated)
    def py(self):
        return self._d["py"]

    @pyqtProperty(float, notify=viewUpdated)
    def pz(self):
        return self._d["pz"]

    @pyqtProperty(float, notify=viewUpdated)
    def yaw(self):
        return self._d["yaw"]

    @pyqtProperty(float, notify=viewUpdated)
    def pitch(self):
        return self._d["pitch"]

    @pyqtProperty(float, notify=viewUpdated)
    def cx(self):
        return self._d["cx"]

    @pyqtProperty(float, notify=viewUpdated)
    def cy(self):
        return self._d["cy"]

    @pyqtProperty(float, notify=viewUpdated)
    def cz(self):
        return self._d["cz"]

    @pyqtProperty(float, notify=viewUpdated)
    def camYaw(self):
        return self._d["camYaw"]

    @pyqtProperty(float, notify=viewUpdated)
    def camPitch(self):
        return self._d["camPitch"]

    @pyqtProperty(float, notify=viewUpdated)
    def cadence(self):
        return self._d["cadence"]

    @pyqtSlot(str)
    def terrainFailed(self, message: str):
        print("[Roue Libre] Échec du chargement du terrain :", message)
        self.terrainError.emit(message)


def _pose_for_view(pose: dict) -> dict:
    return {**pose,
            "yaw_deg": -math.degrees(pose["yaw"]),
            "pitch_deg": math.degrees(pose["pitch"])}


def _camera_for_view(pose: dict) -> dict:
    hd = pose["yaw"]
    dx, dz = math.cos(hd), math.sin(hd)
    cx = pose["x"] - dx * CAM_BACK
    cy = pose["y"] + CAM_UP
    cz = pose["z"] - dz * CAM_BACK
    tx = pose["x"] + dx * CAM_AHEAD
    ty = pose["y"]
    tz = pose["z"] + dz * CAM_AHEAD
    vdx, vdz = tx - cx, tz - cz
    horizontal = math.hypot(vdx, vdz) or 1.0
    cam_yaw = math.degrees(math.atan2(-vdx, -vdz))
    cam_pitch = math.degrees(math.atan2(ty - cy, horizontal))
    return {"x": cx, "y": cy, "z": cz, "yaw_deg": cam_yaw, "pitch_deg": cam_pitch}


class World3DView(QQuickWidget):
    error_occurred = pyqtSignal(str)

    def __init__(self, world, jersey_color="#d95f2b", bike_color="#22262c",
                 parent=None):
        super().__init__(parent)
        self.world = world
        url = QUrl.fromLocalFile(str(world.terrain_path)).toString()
        texture = QUrl.fromLocalFile(str(world.texture_path)).toString()
        self.bridge = WorldBridge(world.theme, url, texture,
                                  jersey_color, bike_color)
        self.rootContext().setContextProperty("worldBridge", self.bridge)
        self.bridge.terrainError.connect(self.error_occurred)
        print("[Roue Libre] Vue 3D : Qt", QT_VERSION_STR, "—",
              world.terrain_path.name)
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.statusChanged.connect(self._on_status)
        self.setSource(QUrl.fromLocalFile(str(QML_PATH)))
        self._on_status(self.status())

    def _on_status(self, status):
        if status == QQuickWidget.Status.Error:
            details = "; ".join(str(e.toString()) for e in self.errors())
            print("[Roue Libre] Vue 3D indisponible, repli sur la vue 2D :", details)
            self.error_occurred.emit(details)

    def update_state(self, snap: dict):
        view_pose = _pose_for_view(self.world.pose_at(snap["distance"]))
        self.bridge.update(snap, view_pose, _camera_for_view(view_pose))
