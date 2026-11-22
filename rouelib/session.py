"""Session de sortie : relie le matériel, le parcours et l'entraînement."""

import time

from .physics import SpeedModel


class RideSession:
    """Fait avancer le cycliste le long du parcours, pas par pas.

    La session est volontairement indépendante de Qt : elle est testable
    hors interface graphique. L'interface appelle simplement tick(dt).
    """

    def __init__(self, route, trainer, settings, workout=None):
        self.route = route
        self.trainer = trainer
        self.settings = settings
        self.workout = workout
        self.mode = "erg" if workout else "sim"
        self.speed_model = SpeedModel(settings)

        self.distance = 0.0
        self.elapsed = 0.0
        self.paused = False
        self.finished = False
        self.route_done = False

        self._power_sum = 0.0
        self._power_max = 0.0
        self._power_samples = 0
        self._hr_sum = 0.0
        self._hr_samples = 0
        self._cadence_sum = 0.0
        self._cadence_samples = 0
        self._sum_start = 0.0
        self.elev_gain = 0.0
        self._last_elev = route.elevation_at(0.0)

        self.w_target = None
        self.seg_index = 0
        self.seg_elapsed = 0.0
        if self.workout and workout.segments:
            first = workout.segments[0]
            self.w_target = round(settings.ftp_w * first.ftp_pct / 100.0)
            trainer.set_target_power(self.w_target)

    # -- boucle de simulation ----------------------------------------------
    def tick(self, dt: float) -> None:
        if self.paused or self.finished or dt <= 0:
            return
        self.elapsed += dt

        power = self.trainer.power or 0.0
        cadence = self.trainer.cadence
        hr = self.trainer.heart_rate

        if self.workout and self.trainer.is_simulated:
            power = max(power, self.w_target or 0.0)

        grade = self.route.grade_at(self.distance)
        speed = self.speed_model.update(dt, power, grade)
        self.distance += speed * dt

        elev = self.route.elevation_at(self.distance)
        if elev > self._last_elev:
            self.elev_gain += elev - self._last_elev
        self._last_elev = elev

        self._accum(power, cadence, hr, dt)

        if self.workout:
            self._tick_workout(dt, power)

        if self.distance >= self.route.length_m:
            self.distance = self.route.length_m
            self.route_done = True
            if not self.workout:
                self.finished = True

    def _tick_workout(self, dt: float, power: float) -> None:
        self.seg_elapsed += dt
        seg = self.workout.segments[self.seg_index]
        if self.seg_elapsed >= seg.duration_s:
            if self.seg_index + 1 >= len(self.workout.segments):
                self.seg_elapsed = seg.duration_s
                self.finished = True
                return
            self.seg_elapsed -= seg.duration_s
            self.seg_index += 1
            seg = self.workout.segments[self.seg_index]
        target = round(self.settings.ftp_w * seg.ftp_pct / 100.0)
        if target != self.w_target:
            self.w_target = target
            self.trainer.set_target_power(target)

    def workout_elapsed(self) -> float:
        return sum(s.duration_s for s in self.workout.segments[:self.seg_index]) \
            + self.seg_elapsed

    def _accum(self, power, cadence, hr, dt) -> None:
        self._power_sum += power * dt
        self._power_samples += dt
        self._power_max = max(self._power_max, power)
        if cadence:
            self._cadence_sum += cadence * dt
            self._cadence_samples += dt
        if hr:
            self._hr_sum += hr * dt
            self._hr_samples += dt

    # -- pilotage ------------------------------------------------------------
    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def effort_adjust(self, delta: float) -> None:
        """Uniquement en mode démo : ajuste l'effort (touches + / -)."""
        if self.trainer.is_simulated:
            self.trainer.set_effort(self.trainer.effort + delta)

    # -- état affiché ----------------------------------------------------------
    def snapshot(self) -> dict:
        power = self.trainer.power or 0.0
        seg = None
        seg_remaining = 0.0
        if self.workout and self.workout.segments:
            seg = self.workout.segments[self.seg_index]
            seg_remaining = max(0.0, seg.duration_s - self.seg_elapsed)
        avg_power = self._power_sum / self._power_samples if self._power_samples else 0.0
        avg_hr = self._hr_sum / self._hr_samples if self._hr_samples else None
        avg_cadence = self._cadence_sum / self._cadence_samples if self._cadence_samples else None
        return {
            "elapsed": self.elapsed,
            "distance": self.distance,
            "remaining": max(0.0, self.route.length_m - self.distance),
            "speed_kmh": self.speed_model.speed * 3.6,
            "power": power,
            "avg_power": avg_power,
            "max_power": self._power_max,
            "heart_rate": self.trainer.heart_rate,
            "avg_hr": avg_hr,
            "cadence": self.trainer.cadence,
            "avg_cadence": avg_cadence,
            "grade_pct": self.route.grade_at(self.distance) * 100.0,
            "elevation": self.route.elevation_at(self.distance),
            "elev_gain": self.elev_gain,
            "w_target": self.w_target,
            "segment": seg,
            "seg_remaining": seg_remaining,
            "seg_index": self.seg_index,
            "paused": self.paused,
            "finished": self.finished,
            "route_done": self.route_done,
        }

    def summary(self) -> dict:
        snap = self.snapshot()
        return {
            "ts": time.time(),
            "activity": "Entraînement" if self.workout else "Sortie libre",
            "route_name": self.route.name,
            "duration_s": snap["elapsed"],
            "distance_m": snap["distance"],
            "avg_power": round(snap["avg_power"]),
            "max_power": round(snap["max_power"]),
            "avg_hr": round(snap["avg_hr"]) if snap["avg_hr"] else None,
            "avg_cadence": round(snap["avg_cadence"]) if snap["avg_cadence"] else None,
            "elev_gain": round(snap["elev_gain"]),
        }
