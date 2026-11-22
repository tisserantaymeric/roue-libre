"""Modèle physique : convertit la puissance en vitesse selon la pente.

L'équation du mouvement d'un cycliste est intégrée pas à pas :

  m·dv/dt = P_roue/v − 0,5·ρ·CdA·v² − m·g·cos θ·Crr − m·g·sin θ
"""

import math
from dataclasses import dataclass, asdict

RHO_AIR = 1.225
G = 9.81
MAX_SPEED_MS = 30.0


@dataclass
class RiderSettings:
    rider: str = "Cycliste"
    weight_kg: float = 78.0
    bike_kg: float = 10.0
    ftp_w: float = 200.0
    cda: float = 0.40
    crr: float = 0.004
    drivetrain_loss: float = 0.03

    def total_mass(self) -> float:
        return self.weight_kg + self.bike_kg

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RiderSettings":
        merged = {f.name: data[f.name] for f in cls.__dataclass_fields__.values()
                  if f.name in data and data[f.name] is not None}
        return cls(**merged)


class SpeedModel:
    """Intègre la vitesse du cycliste à partir de sa puissance."""

    def __init__(self, settings: RiderSettings):
        self.settings = settings
        self.speed = 0.0

    def reset(self) -> None:
        self.speed = 0.0

    def update(self, dt: float, power_w: float, grade: float) -> float:
        """Avance le modèle de dt secondes et renvoie la vitesse (m/s).

        :param power_w: puissance fournie par le cycliste (watts)
        :param grade: pente en fraction (0.06 = 6 %), négative en descente
        """
        s = self.settings
        mass = s.total_mass()
        p_wheel = power_w * (1.0 - s.drivetrain_loss) if power_w > 0 else 0.0
        theta = math.atan(grade)

        if self.speed > 0.2:
            drag = 0.5 * RHO_AIR * s.cda * self.speed ** 2
            roll = mass * G * math.cos(theta) * s.crr
            acct = (p_wheel / self.speed) - drag - roll - mass * G * math.sin(theta)
            a = acct / mass
        else:
            ref = 0.6
            a = (p_wheel / ref
                 - mass * G * math.sin(theta)
                 - mass * G * math.cos(theta) * s.crr) / mass
            if a < 0:
                a = 0.0

        self.speed = min(MAX_SPEED_MS, max(0.0, self.speed + a * dt))
        return self.speed
