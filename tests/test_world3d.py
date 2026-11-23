import json
import math

from pathlib import Path

from rouelib.routes import route_from_dict
from rouelib.world3d import (FORMAT_VERSION, STEP_ACROSS, STEP_ALONG,
                             TERRAIN_HALF_WIDTH, World, _write_png_rgb,
                             build_world, read_png_rgb)


def _route(length_km=9.0, grade=2.0):
    return route_from_dict({"name": "Test Col",
                            "segments": [{"km": length_km, "grade": grade}]})


def test_build_world_files_and_meta(tmp_path):
    world = build_world(_route(), cache_dir=tmp_path)
    assert world.terrain_path.exists()
    assert world.texture_path.exists()
    assert world.length_m == 9000.0
    meta = (Path(world.directory) / "monde.json")
    assert meta.exists()
    parsed = json.loads(meta.read_text())
    assert parsed["version"] == FORMAT_VERSION


def test_centerline_matches_route_elevation(tmp_path):
    route = _route()
    world = build_world(route, cache_dir=tmp_path)
    for dist in (0.0, 4500.0, 8999.0):
        pose = world.pose_at(dist)
        assert abs(pose["y"] - route.elevation_at(dist)) < 0.6
        assert math.isfinite(pose["x"]) and math.isfinite(pose["z"])


def test_pose_moves_forward(tmp_path):
    world = build_world(_route(), cache_dir=tmp_path)
    p0, p1, p2 = (world.pose_at(s) for s in (0.0, 4500.0, 9000.0))
    assert p1["x"] > p0["x"]
    assert p2["x"] > p1["x"]
    assert abs(p1["y"] - 90.0) < 5.0


def test_curves_stay_bounded(tmp_path):
    world = build_world(_route(12.0), cache_dir=tmp_path)
    yaws = [world.pose_at(s)["yaw"] for s in range(0, 12000, 100)]
    assert max(yaws) < math.pi / 2 + 0.3
    assert min(yaws) > -math.pi / 2 - 0.3


def test_glb_is_well_formed(tmp_path):
    import struct as _struct
    world = build_world(_route(), cache_dir=tmp_path)
    data = world.terrain_path.read_bytes()
    magic, version, total = _struct.unpack_from("<III", data, 0)
    assert magic == 0x46546C67 and version == 2 and total == len(data)
    json_len, json_type = _struct.unpack_from("<II", data, 12)
    assert json_type == 0x4E4F534A
    gltf = json.loads(data[20:20 + json_len].decode("utf-8"))
    primitive = gltf["meshes"][0]["primitives"][0]
    n_vertices = gltf["accessors"][primitive["attributes"]["POSITION"]]["count"]
    n_indices = gltf["accessors"][primitive["indices"]]["count"]
    n_cols = int(TERRAIN_HALF_WIDTH * 2 / STEP_ACROSS) + 1
    assert n_vertices > 1000 and n_vertices % n_cols == 0
    n_rows = n_vertices // n_cols
    assert n_indices == 6 * (n_rows - 1) * (n_cols - 1)
    assert gltf["images"][0]["mimeType"] == "image/png"
    assert "uri" not in gltf["images"][0]
    bin_len, bin_type = _struct.unpack_from("<II", data, 20 + json_len)
    assert bin_type == 0x004E4942
    buffers = gltf["buffers"][0]["byteLength"]
    assert 0 <= bin_len - buffers < 4


def test_texture_road_and_grass(tmp_path):
    world = build_world(_route(), cache_dir=tmp_path)
    width, height, data = read_png_rgb(world.texture_path)
    assert (width, height) == (2048, 256)
    mid_row = height // 2
    center_px = (mid_row * width + width // 2) * 3
    r, g, b = data[center_px:center_px + 3]
    assert abs(r - g) < 12 and abs(g - b) < 14
    corner = (0 * width + 5) * 3
    r2, g2, b2 = data[corner:corner + 3]
    assert max(r2, g2, b2) - min(r2, g2, b2) < 25
    grass_px = (31 * width + 5) * 3
    r3, g3, b3 = data[grass_px:grass_px + 3]
    assert g3 >= r3 and g3 >= b3


def test_png_roundtrip(tmp_path):
    path = tmp_path / "t.png"
    data = bytes(((i * 7) % 256) for i in range(12 * 8 * 3))
    _write_png_rgb(path, 12, 8, data)
    w, h, back = read_png_rgb(path)
    assert (w, h) == (12, 8) and back == data


def test_cache_reuse(tmp_path):
    route = _route()
    first = build_world(route, cache_dir=tmp_path)
    stamp = first.terrain_path.stat().st_mtime_ns
    second = build_world(route, cache_dir=tmp_path)
    assert second.directory == first.directory
    assert second.terrain_path.stat().st_mtime_ns == stamp
