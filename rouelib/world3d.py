"""Génération du monde 3D (palier 1) : terrain maillé + texture + cache.

Le terrain s'organise autour de la route :
  - axe « s » : distance le long du parcours (courbes douces intégrées)
  - axe « latéral » : de −400 m à +400 m autour de la route
La hauteur au centre de la route est exactement celle du parcours, ce qui
garantit que la pente affichée est la pente réellement envoyée au home trainer.

Sorties (mises en cache par parcours) :
  - terrain.glb      maillage terrain + route (normales, UV, glTF 2.0)
  - couleurs.png     texture 2048×256 : herbe, rochers, route, marquage
  - monde.json       ligne centrale échantillonnée, thème, paramètres
"""

import hashlib
import json
import math
import re
import struct
import zlib
from pathlib import Path

from . import storage
from .routes import DEFAULT_THEME, Route

WORLDS_DIR = storage.DATA_DIR / "worlds"

TERRAIN_HALF_WIDTH = 400.0
STEP_ALONG = 25.0
STEP_ACROSS = 20.0
ROAD_HALF_WIDTH = 3.5
MARGIN = 150.0

TEX_WIDTH = 2048
TEX_HEIGHT = 256

FORMAT_VERSION = 2


def _hash01(n: float) -> float:
    x = math.sin(n * 127.1) * 43758.5453
    return x - math.floor(x)


def _fbm(x: float, y: float) -> float:
    total = 0.0
    amp = 0.55
    freq = 1.0
    for octave in range(4):
        ix, iy = math.floor(x * freq), math.floor(y * freq)
        fx, fy = x * freq - ix, y * freq - iy
        n00 = _hash01(ix * 57.0 + iy * 131.0)
        n10 = _hash01((ix + 1) * 57.0 + iy * 131.0)
        n01 = _hash01(ix * 57.0 + (iy + 1) * 131.0)
        n11 = _hash01((ix + 1) * 57.0 + (iy + 1) * 131.0)
        sx = fx * fx * (3 - 2 * fx)
        sy = fy * fy * (3 - 2 * fy)
        total += amp * ((n00 * (1 - sx) + n10 * sx) * (1 - sy)
                        + (n01 * (1 - sx) + n11 * sx) * sy)
        amp *= 0.5
        freq *= 2.3
    return (total * 2.0 - 1.0)


def _ramp(value: float, lo: float, hi: float) -> float:
    if value <= lo:
        return 0.0
    if value >= hi:
        return 1.0
    t = (value - lo) / (hi - lo)
    return t * t * (3 - 2 * t)


def _heading(theta_s: float, length_m: float) -> float:
    """Angle de cap (radians) au kilomètre theta_s : virages doux bornés."""
    wave = max(length_m, 2500.0)
    return (0.55 * math.sin(2 * math.pi * theta_s / wave)
            + 0.18 * math.sin(2 * math.pi * 2.5 * theta_s / wave + 1.3))


def _centerline(route: Route, step: float):
    """Échantillonne la ligne centrale : positions 3D, cap et pente."""
    length = route.length_m
    n = max(16, int(round(length / step)))
    ds = length / n
    xs, ys, zs, hds, grad = [], [], [], [], []
    x = z = 0.0
    for i in range(n + 1):
        s = min(length, i * ds)
        hd = _heading(s, length)
        xs.append(x)
        zs.append(z)
        ys.append(route.elevation_at(s))
        hds.append(hd)
        grad.append(route.grade_at(s))
        x += math.cos(hd) * ds
        z += math.sin(hd) * ds
    return {"ds": ds, "x": xs, "y": ys, "z": zs, "heading": hds, "grade": grad}


class World:
    """Monde 3D prêt à afficher, reconstruit depuis son cache disque."""

    def __init__(self, directory: Path, meta: dict):
        self.directory = Path(directory)
        self.meta = meta
        self.theme = meta["theme"]
        self.length_m = float(meta["length"])
        self._x = [float(v) for v in meta["centerline"]["x"]]
        self._y = [float(v) for v in meta["centerline"]["y"]]
        self._z = [float(v) for v in meta["centerline"]["z"]]
        self._h = [float(v) for v in meta["centerline"]["heading"]]
        self._g = [float(v) for v in meta["centerline"]["grade"]]
        self._ds = float(meta["centerline"]["ds"])

    @property
    def terrain_path(self) -> Path:
        return self.directory / "terrain.glb"

    @property
    def texture_path(self) -> Path:
        return self.directory / "couleurs.png"

    def _pose(self, i0: int, i1: int, frac: float) -> dict:
        x = self._x[i0] + (self._x[i1] - self._x[i0]) * frac
        y = self._y[i0] + (self._y[i1] - self._y[i0]) * frac
        z = self._z[i0] + (self._z[i1] - self._z[i0]) * frac
        heading = self._h[i0] + (self._h[i1] - self._h[i0]) * frac
        grade = self._g[i0] + (self._g[i1] - self._g[i0]) * frac
        return {"x": x, "y": y, "z": z, "yaw": heading,
                "pitch": math.atan(grade), "grade": grade}

    def pose_at(self, distance: float) -> dict:
        s = min(max(distance, 0.0), self.length_m)
        exact = s / max(self._ds, 1e-6)
        i0 = min(int(exact), len(self._x) - 1)
        i1 = min(i0 + 1, len(self._x) - 1)
        return self._pose(i0, i1, exact - i0)


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return slug[:40] or "parcours"


def _cache_key(route: Route) -> str:
    sample = [round(route.elevation_at(route.length_m * i / 40.0), 1)
              for i in range(41)]
    payload = f"{FORMAT_VERSION}|{route.name}|{route.length_m:.1f}|{sample}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def _terrain_height(route: Route, s: float, lat: float, end_grade: float,
                    start_grade: float) -> float:
    length = route.length_m
    if s < 0:
        base = route.elevation_at(0.0) + start_grade * s
    elif s > length:
        base = route.elevation_at(length) + end_grade * (s - length)
    else:
        base = route.elevation_at(s)
    off = abs(lat)
    ramp = _ramp(off, 4.0, 12.0)
    dip = -2.5 * math.exp(-((off - 6.0) / 5.0) ** 2)
    valley = -90.0 * (off / TERRAIN_HALF_WIDTH) ** 2
    hills = 34.0 * (off / TERRAIN_HALF_WIDTH) ** 0.8 * _fbm(s * 0.010, lat * 0.030)
    ridge = 0.0
    if off > 260.0:
        ridge = (off - 260.0) * (0.16 + 0.10 * _fbm(s * 0.004, lat * 0.25))
        ridge = min(ridge, 150.0)
    return base + ramp * (dip + valley + hills + ridge)


def _build_mesh(route: Route, center: dict):
    length = route.length_m
    end_grade = route.grade_at(length - 40.0)
    start_grade = route.grade_at(40.0)
    n_cols = int(TERRAIN_HALF_WIDTH * 2 / STEP_ACROSS) + 1
    lats = [(-TERRAIN_HALF_WIDTH + j * STEP_ACROSS)
            for j in range(n_cols)]

    xs, ys, zs = center["x"], center["y"], center["z"]
    hs = center["heading"]
    ds = center["ds"]
    total_s = length + 2 * MARGIN
    rows = []
    s = -MARGIN
    while s < length + MARGIN:
        rows.append(s)
        s += STEP_ALONG
    rows.append(length + MARGIN)

    verts = []
    for s in rows:
        if s <= 0:
            x0, y0, z0, h0 = xs[0], ys[0], zs[0], hs[0]
        elif s >= length:
            x0, y0, z0, h0 = xs[-1], ys[-1], zs[-1], hs[-1]
        else:
            exact = s / ds
            i0 = min(int(exact), len(xs) - 1)
            i1 = min(i0 + 1, len(xs) - 1)
            frac = exact - i0
            x0 = xs[i0] + (xs[i1] - xs[i0]) * frac
            y0 = ys[i0] + (ys[i1] - ys[i0]) * frac
            z0 = zs[i0] + (zs[i1] - zs[i0]) * frac
            h0 = hs[i0] + (hs[i1] - hs[i0]) * frac
        px, pz = -math.sin(h0), math.cos(h0)
        row = []
        for lat in lats:
            height = _terrain_height(route, s, lat, end_grade, start_grade)
            row.append((x0 + px * lat, height, z0 + pz * lat))
        rows_u = (s + MARGIN) / total_s
        verts.append((row, rows_u))

    pts = [p for row, _u in verts for p in row]
    n_rows = len(verts)
    n_cols = len(lats)

    normals = []
    for i in range(n_rows):
        for j in range(n_cols):
            i_prev, i_next = max(0, i - 1), min(n_rows - 1, i + 1)
            j_prev, j_next = max(0, j - 1), min(n_cols - 1, j + 1)
            a = (pts[i_next * n_cols + j][0] - pts[i_prev * n_cols + j][0],
                 pts[i_next * n_cols + j][1] - pts[i_prev * n_cols + j][1],
                 pts[i_next * n_cols + j][2] - pts[i_prev * n_cols + j][2])
            b = (pts[i * n_cols + j_next][0] - pts[i * n_cols + j_prev][0],
                 pts[i * n_cols + j_next][1] - pts[i * n_cols + j_prev][1],
                 pts[i * n_cols + j_next][2] - pts[i * n_cols + j_prev][2])
            nx = a[1] * b[2] - a[2] * b[1]
            ny = a[2] * b[0] - a[0] * b[2]
            nz = a[0] * b[1] - a[1] * b[0]
            if ny < 0:
                nx, ny, nz = -nx, -ny, -nz
            norm = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            normals.append((nx / norm, ny / norm, nz / norm))

    return verts, lats, normals


def _write_glb(path: Path, verts, lats, normals):
    """Exporte le terrain au format GLB (glTF 2.0 binaire, lu par Quick 3D)."""
    n_rows, n_cols = len(verts), len(lats)
    positions = bytearray()
    normals_data = bytearray()
    uvs = bytearray()
    for row, u in verts:
        for j, (x, y, z) in enumerate(row):
            positions += struct.pack("<3f", x, y, z)
            uvs += struct.pack("<2f", u, j / (n_cols - 1))
    for nx, ny, nz in normals:
        normals_data += struct.pack("<3f", nx, ny, nz)
    indices = bytearray()
    for i in range(n_rows - 1):
        for j in range(n_cols - 1):
            a = i * n_cols + j
            b = (i + 1) * n_cols + j
            c = (i + 1) * n_cols + j + 1
            d = i * n_cols + j + 1
            indices += struct.pack("<3I", a, b, c)
            indices += struct.pack("<3I", a, c, d)

    xs = [p[0] for row, _u in verts for p in row]
    ys = [p[1] for row, _u in verts for p in row]
    zs = [p[2] for row, _u in verts for p in row]
    n_vertices = n_rows * n_cols
    gltf = {
        "asset": {"version": "2.0", "generator": "Roue Libre"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{
            "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
            "indices": 3, "material": 0, "mode": 4}]}],
        "materials": [{"pbrMetallicRoughness": {
            "baseColorTexture": {"index": 0},
            "metallicFactor": 0.0, "roughnessFactor": 0.95},
            "doubleSided": True}],
        "textures": [{"sampler": 0, "source": 0}],
        "images": [{"uri": "couleurs.png"}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987,
                      "wrapS": 10497, "wrapT": 10497}],
        "buffers": [{"byteLength": len(positions) + len(normals_data)
                     + len(uvs) + len(indices)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(positions),
             "target": 34962},
            {"buffer": 0, "byteOffset": len(positions),
             "byteLength": len(normals_data), "target": 34962},
            {"buffer": 0, "byteOffset": len(positions) + len(normals_data),
             "byteLength": len(uvs), "target": 34962},
            {"buffer": 0, "byteOffset": len(positions) + len(normals_data)
             + len(uvs), "byteLength": len(indices), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": n_vertices,
             "type": "VEC3", "min": [min(xs), min(ys), min(zs)],
             "max": [max(xs), max(ys), max(zs)]},
            {"bufferView": 1, "componentType": 5126, "count": n_vertices,
             "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": n_vertices,
             "type": "VEC2"},
            {"bufferView": 3, "componentType": 5125,
             "count": (n_rows - 1) * (n_cols - 1) * 6, "type": "SCALAR"},
        ],
    }

    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    bin_chunk = bytes(positions + normals_data + uvs + indices)
    bin_chunk += b"\x00" * ((4 - len(bin_chunk) % 4) % 4)
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    path.write_bytes(
        struct.pack("<III", 0x46546C67, 2, total)
        + struct.pack("<II", len(json_chunk), 0x4E4F534A) + json_chunk
        + struct.pack("<II", len(bin_chunk), 0x004E4942) + bin_chunk)


def _write_texture(path: Path, route: Route):
    theme = route.theme if hasattr(route, "theme") else DEFAULT_THEME
    total_s = route.length_m + 2 * MARGIN
    road_h = int(round(ROAD_HALF_WIDTH / (2 * TERRAIN_HALF_WIDTH / TEX_HEIGHT)))

    def grass(px, py):
        n = _hash01(px * 0.37 + py * 61.7) * 0.5 + _fbm(px / 90.0, py / 26.0) * 0.25
        base = (0x4e, 0x7a, 0x45)
        tone = int(14 * (n - 0.5))
        return (max(0, min(255, base[0] + tone)),
                max(0, min(255, base[1] + tone)),
                max(0, min(255, base[2] + tone // 2)))

    def rock(px, py):
        n = _hash01(px * 0.19 + py * 23.1)
        base = (0x5c, 0x59, 0x54)
        tone = int(20 * (n - 0.5))
        return (base[0] + tone, base[1] + tone, base[2] + tone)

    raw = bytearray()
    for j in range(TEX_HEIGHT):
        lat = TERRAIN_HALF_WIDTH - (j + 0.5) * (2 * TERRAIN_HALF_WIDTH / TEX_HEIGHT)
        off = abs(lat)
        meters_per_px_s = total_s / TEX_WIDTH
        for i in range(TEX_WIDTH):
            s = i * meters_per_px_s
            if off <= ROAD_HALF_WIDTH:
                dashes = (int(s / 6.0) % 2) == 0 and abs(lat) < 0.20
                edges = abs(abs(lat) - (ROAD_HALF_WIDTH - 0.35)) < 0.20
                if dashes or edges and off > 1.0:
                    val = 235
                    raw += bytes((val, val, val))
                else:
                    n = _hash01(i * 0.61 + j * 7.3)
                    g = 0x48 + int(8 * n)
                    raw += bytes((g, g + 2, g + 6))
            elif off <= ROAD_HALF_WIDTH + 2.5:
                n = _hash01(i * 0.25 + j * 3.1)
                base = 0x6b + int(10 * (n - 0.5))
                raw += bytes((base, base - 2, base - 10))
            elif off > TERRAIN_HALF_WIDTH - 90.0:
                raw += bytes(rock(i, j))
            else:
                raw += bytes(grass(i, j))
    _write_png_rgb(path, TEX_WIDTH, TEX_HEIGHT, bytes(raw))
    del road_h


def _write_png_rgb(path: Path, width: int, height: int, data: bytes):
    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return (struct.pack(">I", len(payload)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = bytearray()
    stride = width * 3
    for y in range(height):
        rows.append(0)
        rows += data[y * stride:(y + 1) * stride]
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
           + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b""))
    path.write_bytes(png)


def read_png_rgb(path: Path):
    """Décodage PNG minimal (RGB 8 bits, filtres 0/1/2/3) pour les tests."""
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    width = height = None
    idat = bytearray()
    while pos < len(data):
        (length,) = struct.unpack_from(">I", data, pos)
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            width, height = struct.unpack_from(">II", payload, 0)
        elif tag == b"IDAT":
            idat += payload
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    stride = width * 3
    out = bytearray(width * height * 3)
    prev = bytearray(stride)
    offset = 0
    for y in range(height):
        row = bytearray(raw[offset + 1:offset + 1 + stride])
        filt = raw[offset]
        if filt == 1:
            for i in range(3, stride):
                row[i] = (row[i] + row[i - 3]) & 0xFF
        elif filt == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(stride):
                left = row[i - 3] if i >= 3 else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filt == 4:
            for i in range(stride):
                a = row[i - 3] if i >= 3 else 0
                b = prev[i]
                c = prev[i - 3] if i >= 3 else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[i] = (row[i] + pred) & 0xFF
        out[y * stride:(y + 1) * stride] = row
        prev = row
        offset += 1 + stride
    return width, height, bytes(out)


def build_world(route: Route, cache_dir: Path = None) -> World:
    """Construit (ou recharge du cache) le monde 3D correspondant au parcours."""
    worlds_dir = Path(cache_dir) if cache_dir else WORLDS_DIR
    world_dir = worlds_dir / f"{_slug(route.name)}-{_cache_key(route)}"
    marker = world_dir / "monde.json"

    if marker.exists():
        meta = json.loads(marker.read_text(encoding="utf-8"))
        if meta.get("version") == FORMAT_VERSION and (world_dir / "terrain.glb").exists():
            return World(world_dir, meta)

    world_dir.mkdir(parents=True, exist_ok=True)
    center = _centerline(route, STEP_ALONG / 2.0)
    verts, lats, normals = _build_mesh(route, center)
    _write_glb(world_dir / "terrain.glb", verts, lats, normals)
    _write_texture(world_dir / "couleurs.png", route)

    meta = {
        "version": FORMAT_VERSION,
        "route_name": route.name,
        "length": route.length_m,
        "theme": dict(route.theme),
        "centerline": center,
    }
    marker.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return World(world_dir, meta)
