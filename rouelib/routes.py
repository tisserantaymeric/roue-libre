"""Parcours : profils altimétriques réels (GPX) ou fictifs (JSON)."""

import bisect
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

try:
    import gpxpy
    HAS_GPX = True
except ImportError:
    HAS_GPX = False

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ROUTES_DIR = ASSETS_DIR / "routes"
WORKOUTS_DIR = ASSETS_DIR / "workouts"

DEFAULT_THEME = {
    "sky_top": "#1b2a4a",
    "sky_bottom": "#e8896a",
    "hill_far": "#3a4a6b",
    "hill_near": "#2b3a55",
    "ground": "#20301f",
    "road": "#3c3f45",
    "accent": "#f5a623",
    "scenery": "trees",
}


def _smooth(values, window: int):
    """Moyenne glissante qui préserve les extrémités."""
    if window < 2 or len(values) < 3:
        return list(values)
    half = window // 2
    out = []
    for i, _ in enumerate(values):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


@dataclass
class Route:
    name: str
    description: str = ""
    source: str = "builtin"
    theme: dict = field(default_factory=lambda: dict(DEFAULT_THEME))
    distances: list = field(default_factory=list)
    elevations: list = field(default_factory=list)

    @property
    def length_m(self) -> float:
        return self.distances[-1] if self.distances else 0.0

    def elevation_at(self, d: float) -> float:
        if not self.distances:
            return 0.0
        d = min(max(d, 0.0), self.length_m)
        i = bisect.bisect_left(self.distances, d)
        if i <= 0:
            return self.elevations[0]
        if i >= len(self.distances):
            return self.elevations[-1]
        d0, d1 = self.distances[i - 1], self.distances[i]
        e0, e1 = self.elevations[i - 1], self.elevations[i]
        if d1 <= d0:
            return e1
        return e0 + (e1 - e0) * (d - d0) / (d1 - d0)

    def grade_at(self, d: float, span: float = 30.0) -> float:
        """Pente locale en fraction, mesurée sur ±span mètres."""
        e_before = self.elevation_at(max(0.0, d - span))
        e_after = self.elevation_at(min(self.length_m, d + span))
        width = min(self.length_m, d + span) - max(0.0, d - span)
        if width <= 0:
            return 0.0
        return (e_after - e_before) / width

    def elevation_gain(self) -> float:
        gain = 0.0
        for i in range(1, len(self.elevations)):
            d = self.elevations[i] - self.elevations[i - 1]
            if d > 0:
                gain += d
        return gain


def _route_from_points(name, description, source, theme, points):
    points = sorted(points, key=lambda p: p[0])
    distances = [float(d) for d, _ in points]
    raw_elev = [float(e) for _, e in points]
    step = distances[1] - distances[0] if len(distances) > 1 else 1.0
    window = max(3, int(round(50.0 / step)) | 1)
    elevations = _smooth(raw_elev, window)
    return Route(name=name, description=description, source=source,
                 theme=theme or dict(DEFAULT_THEME),
                 distances=distances, elevations=elevations)


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_gpx(path, name=None) -> Route:
    if not HAS_GPX:
        raise RuntimeError("Le module gpxpy est requis pour lire les fichiers GPX.")
    with open(path, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    pts = []
    for track in gpx.tracks:
        for seg in track.segments:
            for p in seg.points:
                ele = p.elevation if p.elevation is not None else 0.0
                pts.append((p.latitude, p.longitude, ele))
    if not pts:
        for route in gpx.routes:
            for p in route.points:
                ele = p.elevation if p.elevation is not None else 0.0
                pts.append((p.latitude, p.longitude, ele))
    if len(pts) < 2:
        raise ValueError("Le fichier GPX ne contient pas assez de points.")

    distances = [0.0]
    for i in range(1, len(pts)):
        d = _haversine(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])
        distances.append(distances[-1] + d)
    points = list(zip(distances, [p[2] for p in pts]))

    title = name or gpx.name or Path(path).stem
    length_km = points[-1][0] / 1000.0
    return _route_from_points(
        name=title,
        description=f"Parcours GPX importé — {length_km:.1f} km",
        source="gpx",
        theme=dict(DEFAULT_THEME),
        points=points,
    )


def route_from_dict(data: dict) -> Route:
    """Construit un parcours fictif depuis un dictionnaire JSON.

    Deux formats acceptés :
      - segments : [{"km": 5, "grade": 2.5}, ...] (grade = pente en %)
      - profile : [0, 12, 30, ...] altimétrie échantillonnée régulièrement
    """
    theme = dict(DEFAULT_THEME)
    theme.update(data.get("theme") or {})
    name = data["name"]
    description = data.get("description", "")

    if "segments" in data:
        distances, elevations = [0.0], [0.0]
        for seg in data["segments"]:
            length_m = float(seg["km"]) * 1000.0
            grade = float(seg.get("grade", 0.0)) / 100.0
            start_e = elevations[-1]
            end_e = start_e + grade * length_m
            distances.append(distances[-1] + length_m)
            elevations.append(end_e)
        points = []
        for i in range(len(distances) - 1):
            steps = max(2, int((distances[i + 1] - distances[i]) // 25))
            for k in range(steps):
                frac = k / steps
                points.append((distances[i] + frac * (distances[i + 1] - distances[i]),
                               elevations[i] + frac * (elevations[i + 1] - elevations[i])))
        points.append((distances[-1], elevations[-1]))
        return _route_from_points(name, description, "builtin", theme, points)

    if "profile" in data:
        sample_m = float(data.get("sample_m", 25.0))
        distances = [i * sample_m for i in range(len(data["profile"]))]
        points = list(zip(distances, [float(e) for e in data["profile"]]))
        return _route_from_points(name, description, "builtin", theme, points)

    raise ValueError(f"Parcours « {name} » : format JSON non reconnu.")


def load_builtin_routes() -> list:
    routes = []
    if ROUTES_DIR.exists():
        for path in sorted(ROUTES_DIR.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    routes.append(route_from_dict(json.load(f)))
            except (ValueError, KeyError, json.JSONDecodeError):
                continue
    return routes
