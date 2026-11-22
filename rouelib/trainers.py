"""Abstraction des home trainers et simulateur de démonstration."""


class TrainerBase:
    """Interface commune : vraie capteur BLE ou simulateur."""

    name = "—"
    is_simulated = False
    supports_power_target = False
    supports_inclination = False
    supports_resistance = False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def set_target_power(self, watts: float) -> None:
        pass

    def set_target_inclination(self, grade: float) -> None:
        pass

    def set_resistance_level(self, level: float) -> None:
        pass

    @property
    def power(self) -> float:
        return 0.0

    @property
    def cadence(self):
        return None

    @property
    def heart_rate(self):
        return None

    @property
    def speed_ms(self):
        return None

    def snapshot(self) -> dict:
        return {"power": self.power, "cadence": self.cadence,
                "heart_rate": self.heart_rate, "speed_ms": self.speed_ms}


class SimTrainer(TrainerBase):
    """Home trainer virtuel : la puissance vient de l'effort (0–100 %)."""

    is_simulated = True

    def __init__(self, ftp_w: float = 200.0):
        self.name = "Simulateur (démo)"
        self.ftp_w = ftp_w
        self._effort = 55.0
        self._cadence = 85.0

    @property
    def effort(self) -> float:
        return self._effort

    def set_effort(self, effort: float) -> None:
        self._effort = min(140.0, max(0.0, effort))
        wobble = 3.0 * (((self._effort * 7.0) % 10.0) / 10.0 - 0.5)
        self._cadence = min(110.0, max(40.0, 70.0 + self._effort * 0.35 + wobble))

    @property
    def power(self) -> float:
        return round(self.ftp_w * self._effort / 100.0)

    @property
    def cadence(self) -> float:
        return self._cadence
