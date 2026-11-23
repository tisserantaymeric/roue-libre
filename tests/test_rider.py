import math

from rouelib.rider import (BB, CRANK_RADIUS, HIP, SHIN_L, THIGH_L, advance_crank,
                           leg_pose, pedal_point)


def test_pedal_point_stays_on_crank_circle():
    for crank in range(0, 360, 10):
        fx, fy = pedal_point(float(crank))
        assert abs(math.hypot(fx - BB[0], fy - BB[1]) - CRANK_RADIUS) < 1e-9
    assert pedal_point(0.0) == (BB[0], BB[1] + CRANK_RADIUS)
    assert abs(pedal_point(90.0)[0] - CRANK_RADIUS) < 1e-9


def test_advance_crank():
    assert advance_crank(0.0, 90.0, 1.0) == 180.0
    assert advance_crank(359.0, 60.0, 1.0 / 60.0) == 5.0
    assert advance_crank(0.0, 0.0, 5.0) == 0.0


def test_leg_segments_keep_their_lengths():
    for crank in range(0, 360, 5):
        pose = leg_pose(float(crank))
        kx, ky = pose["knee"]
        fx, fy = pose["foot"]
        thigh = math.hypot(kx - HIP[0], ky - HIP[1])
        shin = math.hypot(fx - kx, fy - ky)
        assert abs(thigh - THIGH_L) < 1e-6, (crank, thigh)
        assert abs(shin - SHIN_L) < 1e-6, (crank, shin)


def test_knee_points_forward():
    for crank in range(0, 360, 5):
        kx, ky = leg_pose(float(crank))["knee"]
        assert kx > HIP[0] + 0.05, crank


def test_foot_reaches_the_pedal():
    for crank in range(0, 360, 7):
        pose = leg_pose(float(crank))
        assert math.hypot(pose["foot"][0] - pedal_point(crank)[0]) < 1e-6
        assert math.hypot(pose["foot"][1] - pedal_point(crank)[1]) < 1e-6


def test_angles_follow_qml_convention():
    pose = leg_pose(0.0)
    thigh_deg = pose["thigh_z"]
    ux = math.sin(math.radians(thigh_deg))
    uy = -math.cos(math.radians(thigh_deg))
    kx, ky = pose["knee"]
    assert abs(ux - (kx - HIP[0]) / THIGH_L) < 1e-6
    assert abs(uy - (ky - HIP[1]) / THIGH_L) < 1e-6


def test_legs_move_smoothly():
    previous = leg_pose(0.0)
    for crank in range(10, 360, 10):
        current = leg_pose(float(crank))
        for key in ("thigh_z", "knee_z"):
            delta = abs(current[key] - previous[key])
            assert delta < 25.0, (crank, key, delta)
        previous = current


def test_opposite_legs_differ_and_stay_reachable():
    a = leg_pose(0.0, 0.0)
    b = leg_pose(0.0, 180.0)
    assert not math.isclose(a["thigh_z"], b["thigh_z"])
    assert math.isclose(a["foot"][0], pedal_point(0.0)[0])
    assert math.isclose(b["foot"][1], pedal_point(0.0, 180.0)[1])
    for pose in (a, b):
        assert 0.0 < pose["thigh_z"] < 120.0
