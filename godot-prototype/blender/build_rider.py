"""Construction parametrique du coureur + velo, export glTF pour Godot.

Jalon 1 du prototype Godot de Roue Libre. Le modele est volontairement
stylise (low-poly propre) : chaque piece est une piece de mobilier 3D
primitive assemblée et reperee par son nom, car Godot pilote les pivots
(CrankR, CrankL, HipL, KneeL, HipR, KneeR, WheelF, WheelR) par leur nom.

Le pedlage est anime cote Godot (meme cinetmatique que rouelib/rider.py),
aucune animation n'est donc bakee dans le fichier.

Usage :
    blender --background --python build_rider.py

Le fichier ../godot/assets/rider.glb est ecrit, pret a etre ouvert par Godot.
Toutes les dimensions sont en metres. Repere Blender : +Y = avant du velo,
+Z = haut du sol, +X = cote droit.
"""

import math
import os

import bpy
from mathutils import Vector

PARAMS = {
    # Velo
    "wheel_radius": 0.34,
    "wheelbase_half": 0.55,      # entraxe demi (essieu arriere -0.55, avant +0.55)
    "bb_forward": 0.0,           # boitier de pedalier, coordonnee avant
    "bb_height": 0.30,
    "crank_radius": 0.17,
    "crank_side": 0.09,          # demi-largeur des manivelles
    "head_top": (0.47, 0.95),    # tete de direction (avant, haut)
    "head_bottom": (0.50, 0.34),
    "saddle": (-0.18, 0.98),     # point
    # Coureur (meme constantes que rouelib/rider.py)
    "hip": (-0.15, 1.00),
    "thigh_l": 0.46,
    "shin_l": 0.46,
    "thickness": 0.11,
    "leg_side": 0.10,
    # Couleurs RGB
    "bike_color": (0.09, 0.09, 0.11),
    "tire_color": (0.04, 0.04, 0.04),
    "rim_color": (0.75, 0.75, 0.78),
    "jersey_color": (0.85, 0.15, 0.12),
    "skin_color": (0.87, 0.67, 0.52),
    "shorts_color": (0.12, 0.12, 0.15),
    "shoe_color": (0.95, 0.95, 0.95),
}


# ---------------------------------------------------------------------------
# Aides de construction
# ---------------------------------------------------------------------------

def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def make_material(name, color, roughness=0.6, metallic=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def _attach(obj, name, mat):
    obj.name = name
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def add_cylinder(p1, p2, radius, name, mat, sides=16):
    mid = (Vector(p1) + Vector(p2)) / 2.0
    direction = Vector(p2) - Vector(p1)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=sides, radius=radius, depth=max(direction.length, 1e-4),
        location=mid)
    obj = bpy.context.active_object
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    return _attach(obj, name, mat)


def add_box(center, size, name, mat, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center, rotation=rotation)
    obj = bpy.context.active_object
    obj.scale = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    return _attach(obj, name, mat)


def add_sphere(center, radius, name, mat, segments=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=12,
                                         radius=radius, location=center)
    obj = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    return _attach(obj, name, mat)


def add_torus(center, major_r, minor_r, name, mat):
    """Anneau d'axe +X (roue de velo)."""
    bpy.ops.mesh.primitive_torus_add(major_radius=major_r, minor_radius=minor_r,
                                     location=center)
    obj = bpy.context.active_object
    obj.rotation_euler = (0.0, 1.57079632679, 0.0)
    obj = _attach(obj, name, mat)
    return obj


def add_armspin_disc(center, radius, thickness, name, mat):
    """Disque de jante tourne pour avoir son axe sur +X."""
    obj = add_cylinder((center[0] - 0.004, center[1], center[2]),
                       (center[0] + 0.004, center[1], center[2]),
                       radius, name, mat, sides=24)
    return obj


def add_empty(name, location):
    bpy.ops.object.empty_add(type="PLAIN_AXES", scale=(0.05, 0.05, 0.05),
                             location=location)
    obj = bpy.context.active_object
    obj.name = name
    return obj


def parent_keep_world(child, parent_obj):
    child.parent = parent_obj
    child.matrix_parent_inverse = parent_obj.matrix_world.inverted()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def fp(fwd, up, side=0.0):
    """Convertisseur (avant, haut) -> point 3D Blender (x, y, z)."""
    return (side, fwd, up)


def build_bike(p):
    mats = {
        "bike": make_material("MatBike", p["bike_color"], 0.35, 0.3),
        "tire": make_material("MatTire", p["tire_color"], 0.9),
        "rim": make_material("MatRim", p["rim_color"], 0.35, 0.6),
    }
    bike = add_empty("Bike", (0.0, 0.0, 0.0))

    wheel_r = p["wheel_radius"]
    rear = fp(-p["wheelbase_half"], wheel_r)
    front = fp(p["wheelbase_half"], wheel_r)
    hf = p["head_top"]
    hb = p["head_bottom"]
    sad = p["saddle"]
    bb = (p["bb_forward"], p["bb_height"])
    cs = p["crank_side"]

    def axle(center, suffix):
        wheel = add_empty("Wheel" + suffix, center)
        r_in = wheel_r - 0.035
        tire = add_torus(center, r_in + 0.02, 0.023, "Tire" + suffix, mats["tire"])
        rim = add_armspin_disc(center, r_in, 0.008, "Rim" + suffix, mats["rim"])
        hub = add_cylinder((center[0] - 0.05, center[1], center[2]),
                           (center[0] + 0.05, center[1], center[2]),
                           0.025, "Hub" + suffix, mats["rim"], sides=10)
        radius = r_in * 0.93
        for i, angle in enumerate((0.0, 0.6, 1.2, 1.8, 2.4, 3.0)):
            tip = (center[0], center[1] + radius * math.sin(angle),
                   center[2] + radius * math.cos(angle))
            spoke = add_cylinder((center[0], center[1], center[2]), tip, 0.004,
                                 "Spoke%d%s" % (i, suffix), mats["rim"], sides=6)
            parent_keep_world(spoke, wheel)
        parent_keep_world(tire, wheel)
        parent_keep_world(rim, wheel)
        parent_keep_world(hub, wheel)
        return wheel

    wheel_f = axle(front, "F")
    wheel_r = axle(rear, "R")

    # Cadre : tube de selle, tube diagonal, tube superieur, tete de direction,
    # fourche, bases et haubans ; les points sont (cote, avant, haut).
    for name, p1, p2, rad in [
        ("SeatTube", fp(bb[0] - 0.02, bb[1]), fp(sad[0], sad[1] - 0.10), 0.022),
        ("DownTube", fp(bb[0], bb[1]), fp(hf[0], hf[1] - 0.10), 0.024),
        ("TopTube", fp(sad[0], sad[1]), fp(hf[0], hf[1]), 0.020),
        ("HeadTube", fp(hf[0] + 0.01, hf[1]), fp(hb[0], hb[1]), 0.024),
        ("Fork", fp(hb[0], hb[1]), front, 0.016),
        ("ChainstayL", fp(bb[0], bb[1], cs), fp(rear[1], rear[2], cs), 0.014),
        ("ChainstayR", fp(bb[0], bb[1], -cs), fp(rear[1], rear[2], -cs), 0.014),
        ("SeatstayL", fp(sad[0], sad[1], cs * 0.6), fp(rear[1], rear[2], cs), 0.012),
        ("SeatstayR", fp(sad[0], sad[1], -cs * 0.6), fp(rear[1], rear[2], -cs), 0.012),
        ("SeatPost", fp(sad[0], sad[1] - 0.10), fp(sad[0], sad[1] - 0.02), 0.014),
    ]:
        cyl = add_cylinder(p1, p2, rad, name, mats["bike"])
        parent_keep_world(cyl, bike)

    saddle = add_box(fp(sad[0], sad[1] - 0.02), (0.10, 0.24, 0.035), "Saddle",
                     mats["bike"])
    parent_keep_world(saddle, bike)

    bar = add_cylinder(fp(hf[0], hf[1] - 0.02, -0.22),
                       fp(hf[0], hf[1] - 0.02, 0.22),
                       0.014, "Handlebar", mats["bike"])
    parent_keep_world(bar, bike)

    return bike, wheel_f, wheel_r


def build_crank(p, mats, side_sign, suffix):
    """Manivelle + pedale + chaussure. Repose tendue : armR vers le haut."""
    bb = (p["bb_forward"], p["bb_height"])
    s = p["crank_side"] * side_sign
    crank = add_empty("Crank" + suffix, (s, bb[0], bb[1]))
    up = -side_sign  # manivelle droite (+1) : vers le haut ; gauche : vers le bas

    arm_x = s
    arm_top = (arm_x, bb[0], bb[1])
    arm_bot = (arm_x, bb[0], bb[1] + up * p["crank_radius"])
    arm = add_cylinder(arm_top, arm_bot, 0.016, "Arm" + suffix, mats["bike"])
    pedal_z = arm_bot[2]
    pedal = add_box((arm_x * 1.22, bb[0] + 0.005, pedal_z),
                    (0.13, 0.09, 0.022), "Pedal" + suffix, mats["tire"])
    shoe = add_box((arm_x * 1.22, bb[0] + 0.03, pedal_z + 0.045),
                   (0.075, 0.21, 0.06), "Shoe" + suffix, mats["shoe"])
    parent_keep_world(arm, crank)
    parent_keep_world(pedal, crank)
    parent_keep_world(shoe, crank)
    return crank


def build_leg(p, mats, side_sign, suffix):
    """Cuisse + tibia, pivots Hip<K> et Knee<K>, rest pose verticale."""
    s = p["leg_side"] * side_sign
    hip = (s, p["hip"][0], p["hip"][1])
    hip_obj = add_empty("Hip" + suffix, hip)
    knee = (s, hip[1], hip[2] - p["thigh_l"])
    thigh = add_cylinder(hip, knee, p["thickness"] * 0.5, "Thigh" + suffix,
                         mats["jersey"])
    parent_keep_world(thigh, hip_obj)

    knee_obj = add_empty("Knee" + suffix, knee)
    parent_keep_world(knee_obj, hip_obj)
    ankle = (s, knee[1], knee[2] - p["shin_l"])
    shin = add_cylinder(knee, ankle, p["thickness"] * 0.42, "Shin" + suffix,
                        mats["skin"])
    parent_keep_world(shin, knee_obj)
    return hip_obj, knee_obj


def build_body(p, mats):
    body = add_empty("Body", (0.0, 0.0, 0.0))
    s = p["leg_side"]
    hip = Vector((0.0, p["hip"][0], p["hip"][1] + 0.03))
    shoulder = Vector((0.0, p["hip"][0] + 0.42, p["hip"][1] + 0.42))
    torso = add_cylinder(hip, shoulder, p["thickness"] * 0.75, "Torso",
                         mats["jersey"])
    parent_keep_world(torso, body)

    hips = add_box(hip, (0.20, 0.16, 0.15), "Hips", mats["shorts"])
    parent_keep_world(hips, body)

    head = add_sphere((0.0, p["hip"][0] + 0.52, p["hip"][1] + 0.52), 0.105,
                      "Head", mats["skin"])
    parent_keep_world(head, body)
    for sign, sfx in ((1.0, "R"), (-1.0, "L")):
        sh = Vector((sign * 0.13, shoulder.y - 0.02, shoulder.z))
        arm = add_cylinder(sh, Vector((sign * 0.13, p["head_top"][0], p["head_top"][1])),
                           0.045, "BodyArm" + sfx, mats["jersey"])
        parent_keep_world(arm, body)

    helmet = add_sphere((0.0, p["hip"][0] + 0.53, p["hip"][1] + 0.60), 0.118,
                        "Helmet", mats["bike"])
    helmet.scale = (1.25, 1.1, 0.7)
    parent_keep_world(helmet, body)
    return body


def build_rider(p):
    mats = {
        "bike": make_material("MatBike", p["bike_color"], 0.35, 0.3),
        "tire": make_material("MatTire", p["tire_color"], 0.9),
        "rim": make_material("MatRim", p["rim_color"], 0.35, 0.6),
        "jersey": make_material("MatJersey", p["jersey_color"], 0.7),
        "skin": make_material("MatSkin", p["skin_color"], 0.6),
        "shorts": make_material("MatShorts", p["shorts_color"], 0.7),
        "shoe": make_material("MatShoe", p["shoe_color"], 0.6),
    }
    root = add_empty("Rider", (0.0, 0.0, 0.0))

    bike, wheel_f, wheel_r = build_bike(p)
    crank_r = build_crank(p, mats, 1.0, "R")
    crank_l = build_crank(p, mats, -1.0, "L")
    hip_l, knee_l = build_leg(p, mats, -1.0, "L")
    hip_r, knee_r = build_leg(p, mats, 1.0, "R")
    body = build_body(p, mats)

    for obj in (bike, wheel_f, wheel_r, crank_r, crank_l,
                hip_l, knee_l, hip_r, knee_r, body):
        parent_keep_world(obj, root)

    return root


def export_glb(root, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        export_yup=True,
        export_apply=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        export_extras=True,
    )
    return out_path


def main():
    out = os.environ.get("ROUELIB_GLB_OUT")
    if not out:
        here = os.path.dirname(os.path.abspath(__file__))
        out = os.path.normpath(os.path.join(here, "..", "godot", "assets", "rider.glb"))
    clear_scene()
    root = build_rider(PARAMS)
    export_glb(root, out)
    print("ROUELIB: export termine ->", out)


if __name__ == "__main__":
    main()
