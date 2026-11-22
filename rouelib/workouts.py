"""Programmes d'entraînement : intervalles guidés en mode ERG."""

import json
from dataclasses import dataclass
from pathlib import Path

from .routes import WORKOUTS_DIR


@dataclass
class WorkoutSegment:
    duration_s: float
    ftp_pct: float
    label: str = ""


@dataclass
class Workout:
    name: str
    description: str = ""
    segments: list = None

    def __post_init__(self):
        self.segments = [WorkoutSegment(float(s["duration_s"]), float(s["ftp_pct"]),
                                        s.get("label", ""))
                         for s in (self.segments or [])]

    @property
    def total_duration(self) -> float:
        return sum(s.duration_s for s in self.segments)

    def segment_at(self, t: float) -> tuple:
        """Renvoie (segment, temps écoulé dans le segment, temps restant)."""
        remaining = t
        for seg in self.segments:
            if remaining < seg.duration_s:
                return seg, remaining, seg.duration_s - remaining
            remaining -= seg.duration_s
        return self.segments[-1], self.segments[-1].duration_s, 0.0

    @property
    def finished(self) -> bool:
        return self.total_duration <= 0


def workout_from_dict(data: dict) -> Workout:
    return Workout(name=data["name"], description=data.get("description", ""),
                   segments=data.get("segments", []))


def load_builtin_workouts() -> list:
    workouts = []
    if WORKOUTS_DIR.exists():
        for path in sorted(WORKOUTS_DIR.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    workouts.append(workout_from_dict(json.load(f)))
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
    return workouts
