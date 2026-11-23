"""Cinématique du cycliste 3D (palier 2) : pédalage articulé.

Le vélo est modélisé dans son plan vertical (X = avant, Y = haut) :
 - boîtier de pédalier au point (0, 0.30), manivelles de rayon CRANK_RADIUS,
 - hanches fixes au point HIP (cycliste assis),
 - jambes en liaison à deux segments (cuisse THIGH_L, tibia SHIN_L) : le pied
   suit la pédale, le genou est calculé par intersection de cercles
   (solution « genou vers l'avant »).

Les angles renvoyés (thigh_z, knee_z) suivent la convention eulerRotation.z
de Qt Quick 3D appliquée à un segment pointant vers le bas : une rotation de
angle degrés envoie la direction (0, -1) sur (sin a, -cos a).
"""

import math

BB = (0.0, 0.30)
CRANK_RADIUS = 0.17
HIP = (-0.15, 1.00)
THIGH_L = 0.46
SHIN_L = 0.46
THICKNESS = 0.11

_PRIMITIVE_HEIGHT = 100.0


def advance_crank(crank: float, cadence: float, dt: float) -> float:
    """Fait tourner l'angle de manivelle selon la cadence (tr/min)."""
    return (crank + (cadence / 60.0) * 360.0 * dt) % 360.0


def pedal_point(crank_deg: float, phase_deg: float = 0.0):
    """Position du pied (phase_deg = 0 ou 180) sur le cercle du pédalier."""
    th = math.radians(crank_deg + phase_deg)
    return (BB[0] + CRANK_RADIUS * math.sin(th),
            BB[1] + CRANK_RADIUS * math.cos(th))


def _segment_angle(dx: float, dy: float) -> float:
    """Angle (degrés) d'un segment allant vers (dx, dy) depuis la verticale
    descendante, positif vers l'avant (+X)."""
    return math.degrees(math.atan2(dx, -dy))


def leg_pose(crank_deg: float, phase_deg: float = 0.0) -> dict:
    """Angles QML (degrés) de la cuisse et du tibia pour une phase de pédalage.

    Retourne un dict {"thigh_z", "knee_z", "leg_scale", "knee": (x, y),
    "foot": (x, y)}. Les longueurs de segments sont garanties même si la
    pédale sort de la portée (la jambe se tend au maximum).
    """
    fx, fy = pedal_point(crank_deg, phase_deg)
    span = math.hypot(fx - HIP[0], fy - HIP[1])
    dx, dy = fx - HIP[0], fy - HIP[1]
    norm = span or 1.0
    d = min(max(span, abs(THIGH_L - SHIN_L) + 1e-4), THIGH_L + SHIN_L - 1e-4)
    fx = HIP[0] + dx / norm * d
    fy = HIP[1] + dy / norm * d
    dx, dy = fx - HIP[0], fy - HIP[1]

    cos_a = (THIGH_L ** 2 + d ** 2 - SHIN_L ** 2) / (2.0 * THIGH_L * d)
    a = math.acos(max(-1.0, min(1.0, cos_a)))
    thigh = math.atan2(dx, -dy) + a
    ux_t, uy_t = math.sin(thigh), -math.cos(thigh)
    kx, ky = HIP[0] + THIGH_L * ux_t, HIP[1] + THIGH_L * uy_t

    shin = math.atan2(fx - kx, -(fy - ky))
    return {"thigh_z": math.degrees(thigh),
            "knee_z": math.degrees(shin - thigh),
            "leg_scale": (THIGH_L / _PRIMITIVE_HEIGHT,
                          THICKNESS / 100.0,
                          SHIN_L / _PRIMITIVE_HEIGHT),
            "knee": (kx, ky), "foot": (fx, fy)}
