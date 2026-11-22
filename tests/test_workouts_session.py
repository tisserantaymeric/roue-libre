from rouelib.physics import RiderSettings
from rouelib.routes import route_from_dict
from rouelib.session import RideSession
from rouelib.trainers import SimTrainer
from rouelib.workouts import load_builtin_workouts, workout_from_dict


def test_workout_segments_and_duration():
    workout = workout_from_dict({
        "name": "Test",
        "segments": [{"duration_s": 60, "ftp_pct": 50},
                     {"duration_s": 120, "ftp_pct": 100}],
    })
    assert workout.total_duration == 180.0
    seg, elapsed, remaining = workout.segment_at(70.0)
    assert seg.ftp_pct == 100.0
    assert abs(elapsed - 10.0) < 0.01
    assert abs(remaining - 110.0) < 0.01


def _session(workout=None, ftp=200.0):
    route = route_from_dict({"name": "Plat", "segments": [{"km": 20, "grade": 0.0}]})
    trainer = SimTrainer(ftp_w=ftp)
    settings = RiderSettings(weight_kg=75.0, ftp_w=ftp)
    return RideSession(route, trainer, settings, workout), trainer


def test_free_ride_advances():
    session, _ = _session()
    for _ in range(300):
        session.tick(0.1)
    snap = session.snapshot()
    assert snap["distance"] > 100.0
    assert snap["speed_kmh"] > 15.0
    assert snap["grade_pct"] == 0.0


def test_erg_demo_targets_power():
    workout = workout_from_dict({
        "name": "Test",
        "segments": [{"duration_s": 60, "ftp_pct": 50},
                     {"duration_s": 60, "ftp_pct": 100}],
    })
    session, trainer = _session(workout, ftp=200.0)
    for _ in range(50):
        session.tick(0.1)
    snap = session.snapshot()
    assert snap["w_target"] == 100.0
    for _ in range(700):
        session.tick(0.1)
    snap = session.snapshot()
    assert snap["w_target"] == 200.0
    assert snap["seg_index"] == 1


def test_erg_finishes():
    workout = workout_from_dict({
        "name": "Court", "segments": [{"duration_s": 5, "ftp_pct": 60}]})
    session, trainer = _session(workout)
    for _ in range(80):
        session.tick(0.1)
    assert session.finished


def test_pause_freezes():
    session, _ = _session()
    session.tick(1.0)
    session.toggle_pause()
    session.tick(5.0)
    assert session.snapshot()["elapsed"] == 1.0


def test_route_completion():
    route = route_from_dict({"name": "Micro",
                             "segments": [{"km": 0.2, "grade": 0.0}]})
    session, _ = _session()
    session.route = route
    for _ in range(400):
        session.tick(0.1)
        if session.finished:
            break
    assert session.finished and session.route_done
    summary = session.summary()
    assert summary["distance_m"] == route.length_m


def test_builtin_workouts_load():
    workouts = load_builtin_workouts()
    assert len(workouts) >= 3
    for workout in workouts:
        assert workout.total_duration > 0
        assert all(0 < s.ftp_pct <= 200 for s in workout.segments)
