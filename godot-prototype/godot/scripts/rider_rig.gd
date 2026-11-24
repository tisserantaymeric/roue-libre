extends Node3D
class_name RiderRig

## Animation du coureur par cinématique (port GDScript de rouelib/rider.py).
## Les pivots sont les nœuds nommés exportés par Blender : HipL, KneeL,
## HipR, KneeR, CrankL, CrankR, WheelF, WheelR. Le pédalage est recalculé
## à chaque image, aucune animation n'est bakee dans le .glb.
##
## Convention (identique à rouelib/rider.py) : segments de jambe orientés
## vers le bas au repos ; une rotation positive autour de +X (axe latéral)
## envoie le bas du segment vers l'avant du vélo. Les manivelles tournent
## en sens inverse (rotation négative) afin que les pédales suivent
## exactement les pieds calculés par leg_pose().

const BB := Vector2(0.0, 0.30)
const CRANK_RADIUS := 0.17
const HIP := Vector2(-0.15, 1.00)
const THIGH_LEN := 0.46
const SHIN_LEN := 0.46

const WHEEL_RADIUS := 0.34
const PHASE_L := 0.0
const PHASE_R := 180.0

var _crank_deg := 0.0
var _wheel_angle := 0.0
var _hip_l: Node3D
var _knee_l: Node3D
var _hip_r: Node3D
var _knee_r: Node3D
var _crank_l: Node3D
var _crank_r: Node3D
var _wheel_f: Node3D
var _wheel_r: Node3D


func _ready() -> void:
	_hip_l = find_child("HipL", true, false)
	_knee_l = find_child("KneeL", true, false)
	_hip_r = find_child("HipR", true, false)
	_knee_r = find_child("KneeR", true, false)
	_crank_l = find_child("CrankL", true, false)
	_crank_r = find_child("CrankR", true, false)
	_wheel_f = find_child("WheelF", true, false)
	_wheel_r = find_child("WheelR", true, false)
	for node in [_hip_l, _knee_l, _hip_r, _knee_r,
			_crank_l, _crank_r, _wheel_f, _wheel_r]:
		if node == null:
			push_error("RiderRig : pivot introuvable dans rider.glb")
			set_process(false)
			return
	apply_pose()


## Avance l'animation de `delta` secondes.
## cadence : tr/min du pédalier ; speed : m/s (rotation des roues).
func advance(delta: float, cadence: float, speed: float) -> void:
	if cadence > 0.1:
		_crank_deg = fmod(_crank_deg + (cadence / 60.0) * 360.0 * delta, 360.0)
	_wheel_angle = fmod(_wheel_angle - (speed / WHEEL_RADIUS) * delta, TAU)
	apply_pose()


func apply_pose() -> void:
	var crank_rad := -deg_to_rad(_crank_deg)
	_crank_l.rotation.x = crank_rad
	_crank_r.rotation.x = crank_rad
	var pose_l := leg_pose(_crank_deg, PHASE_L)
	var pose_r := leg_pose(_crank_deg, PHASE_R)
	_hip_l.rotation.x = deg_to_rad(pose_l["thigh_z"])
	_knee_l.rotation.x = deg_to_rad(pose_l["knee_z"])
	_hip_r.rotation.x = deg_to_rad(pose_r["thigh_z"])
	_knee_r.rotation.x = deg_to_rad(pose_r["knee_z"])
	_wheel_f.rotation.x = _wheel_angle
	_wheel_r.rotation.x = _wheel_angle


static func pedal_point(crank_deg: float, phase_deg: float) -> Vector2:
	var th := deg_to_rad(crank_deg + phase_deg)
	return BB + Vector2(CRANK_RADIUS * sin(th), CRANK_RADIUS * cos(th))


## Port fidèle de rouelib.rider.leg_pose : la pédale peut sortir de la
## portée de la jambe ; on la ramène sur le cercle joignable (jambe tendue).
static func leg_pose(crank_deg: float, phase_deg: float) -> Dictionary:
	var p := pedal_point(crank_deg, phase_deg)
	var fx := p.x
	var fy := p.y
	var dx := fx - HIP.x
	var dy := fy - HIP.y
	var span := Vector2(dx, dy).length()
	var norm := span if span > 0.0 else 1.0
	var d := clampf(span, absf(THIGH_LEN - SHIN_LEN) + 1e-4,
			THIGH_LEN + SHIN_LEN - 1e-4)
	fx = HIP.x + dx / norm * d
	fy = HIP.y + dy / norm * d
	dx = fx - HIP.x
	dy = fy - HIP.y

	var cos_a := (THIGH_LEN * THIGH_LEN + d * d - SHIN_LEN * SHIN_LEN) \
			/ (2.0 * THIGH_LEN * d)
	cos_a = clampf(cos_a, -1.0, 1.0)
	var a := acos(cos_a)
	var thigh := atan2(dx, -dy) + a
	var kx := HIP.x + THIGH_LEN * sin(thigh)
	var ky := HIP.y - THIGH_LEN * cos(thigh)
	var shin := atan2(fx - kx, -(fy - ky))
	return {
		"thigh_z": rad_to_deg(thigh),
		"knee_z": rad_to_deg(shin - thigh),
	}
