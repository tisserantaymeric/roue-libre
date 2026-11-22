from rouelib.physics import RiderSettings, SpeedModel


def _settings():
    return RiderSettings(weight_kg=75.0, bike_kg=10.0, ftp_w=200.0)


def test_flat_stabilizes_near_expected_speed():
    model = SpeedModel(_settings())
    speed = 0.0
    for _ in range(600):
        speed = model.update(0.1, 200.0, 0.0)
    kmh = speed * 3.6
    assert 25.0 < kmh < 40.0, f"vitesse inattendue à plat : {kmh:.1f} km/h"


def test_climbing_is_slower():
    flat = SpeedModel(_settings())
    climb = SpeedModel(_settings())
    for _ in range(600):
        flat.update(0.1, 200.0, 0.0)
        climb.update(0.1, 200.0, 0.08)
    assert climb.speed < flat.speed * 0.6


def test_descending_coast_gains_speed():
    coast = SpeedModel(_settings())
    coast.speed = 5.0
    for _ in range(300):
        coast.update(0.1, 0.0, -0.06)
    assert coast.speed > 6.0


def test_stops_when_no_power_uphill():
    model = SpeedModel(_settings())
    model.speed = 3.0
    for _ in range(300):
        model.update(0.1, 0.0, 0.05)
    assert model.speed < 0.5


def test_settings_roundtrip():
    s = _settings().to_dict()
    s2 = RiderSettings.from_dict(s)
    assert s2.weight_kg == 75.0 and s2.ftp_w == 200.0
