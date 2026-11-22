import math

from rouelib.routes import Route, load_builtin_routes, route_from_dict


def segment_route():
    return route_from_dict({
        "name": "Test",
        "segments": [{"km": 10, "grade": 5.0}],
        "theme": {"accent": "#123456"},
    })


def test_length_and_elevation():
    route = segment_route()
    assert abs(route.length_m - 10000.0) < 1.0
    assert abs(route.elevation_at(10000.0) - 500.0) < 5.0


def test_grade_matches_definition():
    route = segment_route()
    assert abs(route.grade_at(5000.0) - 0.05) < 0.005


def test_elevation_gain():
    route = segment_route()
    assert abs(route.elevation_gain() - 500.0) < 5.0


def test_clamp_distances():
    route = segment_route()
    assert route.elevation_at(-100.0) == route.elevation_at(0.0)
    assert route.elevation_at(999999.0) == route.elevation_at(route.length_m)


def test_builtin_routes_load():
    routes = load_builtin_routes()
    names = [r.name for r in routes]
    assert len(routes) >= 4
    assert any("Lac" in n for n in names)
    assert any("Aiguille" in n for n in names)
    for route in routes:
        assert route.length_m > 0
        assert math.isfinite(route.elevation_at(route.length_m / 2))


def test_theme_is_applied():
    route = segment_route()
    assert route.theme["accent"] == "#123456"
    assert route.theme["scenery"] == "trees"
