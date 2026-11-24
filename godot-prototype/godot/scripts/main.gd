extends Node3D

## Jalon 1 du prototype Godot de Roue Libre : coureur GLTF anime par
## cinematique, boucle de route plate, HUD, mode demo (flèches haut/bas).
## La physique puissance -> vitesse est le port de rouelib/physics.py.

const RIDER_SCENE := "res://assets/rider.glb"

const WHEEL_CIRCUMFERENCE_M := 2.136
const GEAR_RATIO := 2.9
const ROAD_WIDTH := 2.4
const ROAD_LIFT := 0.06
const TREE_COUNT := 90
const MAX_POWER_W := 450.0

const CURVE_POINTS := 72
const CURVE_BASE_RADIUS := 82.0

var speed_model: SpeedModel
var power_w := 150.0
var distance_m := 0.0
var loop_len := 0.0
var camera_chase := true

var track: Curve3D
var rider_root: Node3D
var rider_rig: RiderRig
var camera: Camera3D
var hud_data: Label
var hud_help: Label

var _cam_pos: Vector3


func _ready() -> void:
	speed_model = SpeedModel.new()
	_build_environment()
	_build_terrain()
	_build_track()
	_build_rider()
	_build_camera()
	_build_hud()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var key := event as InputEventKey
		if key.keycode == KEY_ESCAPE:
			get_tree().quit()
		elif key.keycode == KEY_F:
			camera_chase = not camera_chase


func _process(delta: float) -> void:
	var power_step := 60.0 * delta
	if Input.is_action_pressed("ui_up"):
		power_w = minf(power_w + power_step, MAX_POWER_W)
	if Input.is_action_pressed("ui_down"):
		power_w = maxf(power_w - power_step, 0.0)

	var speed := speed_model.update(delta, power_w, 0.0)
	distance_m += speed * delta

	var offset := fmod(distance_m, loop_len)
	var pos := track.sample_baked(offset, true)
	var ahead := track.sample_baked(fmod(offset + 2.5, loop_len), true)
	var forward := (ahead - pos).normalized()
	if forward.length_squared() < 0.001:
		forward = Vector3.FORWARD

	rider_root.global_position = pos + Vector3.UP * ROAD_LIFT
	var to_ahead := Transform3D(Basis(), rider_root.global_position) \
			.looking_at(rider_root.global_position + forward, Vector3.UP)
	rider_root.global_basis = to_ahead.basis

	var cadence := _cadence_for(speed)
	rider_rig.advance(delta, cadence, speed)
	_update_camera(delta, pos, forward)
	_update_hud(speed, cadence, offset)


func _cadence_for(speed: float) -> float:
	if speed < 0.2:
		return 0.0
	var rpm := speed / WHEEL_CIRCUMFERENCE_M / GEAR_RATIO * 60.0
	return clampf(rpm, 0.0, 130.0)


# ---------------------------------------------------------------------------
# Construction du monde
# ---------------------------------------------------------------------------

func _build_environment() -> void:
	var env := Environment.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.30, 0.48, 0.75)
	sky_mat.sky_horizon_color = Color(0.72, 0.80, 0.88)
	sky_mat.ground_bottom_color = Color(0.20, 0.26, 0.15)
	sky_mat.ground_horizon_color = Color(0.55, 0.62, 0.48)
	var sky := Sky.new()
	sky.sky_material = sky_mat
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.fog_enabled = true
	env.fog_density = 0.0035
	env.fog_sky_affect = 0.2
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-52.0, -38.0, 0.0)
	sun.light_energy = 1.25
	sun.light_color = Color(1.0, 0.96, 0.88)
	sun.shadow_enabled = true
	add_child(sun)


func _build_terrain() -> void:
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(600.0, 600.0)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.36, 0.47, 0.26)
	mat.roughness = 1.0
	mesh.material = mat
	var ground := MeshInstance3D.new()
	ground.mesh = mesh
	ground.position = Vector3(0.0, -0.02, 0.0)
	add_child(ground)


func _build_track() -> void:
	track = Curve3D.new()
	track.bake_interval = 0.5
	var n := CURVE_POINTS
	var step := TAU / float(n)
	for i in n + 1:
		var a := step * float(i)
		var r := CURVE_BASE_RADIUS + 16.0 * sin(3.0 * a + 0.8) \
				+ 7.0 * sin(5.0 * a + 2.1)
		var pos := Vector3(r * cos(a), 0.0, r * sin(a))
		var tangent := Vector3(
				-r * sin(a) + (16.0 * 3.0 * cos(3.0 * a + 0.8) + 7.0 * 5.0
						* cos(5.0 * a + 2.1)) * cos(a),
				0.0,
				r * cos(a) + (16.0 * 3.0 * cos(3.0 * a + 0.8) + 7.0 * 5.0
						* cos(5.0 * a + 2.1)) * (-sin(a))).normalized()
		var handle := tangent * 10.0
		track.add_point(pos, -handle, handle)

	loop_len = track.get_baked_length()
	_build_road_surface()
	_build_center_line()
	_build_trees()


func _road_frames() -> Dictionary:
	var baked := track.get_baked_points()
	var count := baked.size()
	var positions: Array[Vector3] = []
	var rights: Array[Vector3] = []
	for i in count:
		var prev := baked[maxi(i - 1, 0)]
		var next := baked[mini(i + 1, count - 1)]
		var tangent := (next - prev).normalized()
		positions.append(baked[i])
		rights.append(Vector3(tangent.z, 0.0, -tangent.x))
	return {"positions": positions, "rights": rights}


func _build_road_surface() -> void:
	var frames := _road_frames()
	var positions: Array[Vector3] = frames["positions"]
	var rights: Array[Vector3] = frames["rights"]
	var count := positions.size()
	var half := ROAD_WIDTH / 2.0

	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in count - 1:
		var p_l := positions[i] + rights[i] * half + Vector3.UP * ROAD_LIFT
		var p_r := positions[i] - rights[i] * half + Vector3.UP * ROAD_LIFT
		var q_l := positions[i + 1] + rights[i + 1] * half + Vector3.UP * ROAD_LIFT
		var q_r := positions[i + 1] - rights[i + 1] * half + Vector3.UP * ROAD_LIFT
		st.add_vertex(p_l)
		st.add_vertex(q_l)
		st.add_vertex(p_r)
		st.add_vertex(p_r)
		st.add_vertex(q_l)
		st.add_vertex(q_r)
	st.generate_normals()
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.23, 0.23, 0.25)
	mat.roughness = 0.95
	st.set_material(mat)
	var road := MeshInstance3D.new()
	road.mesh = st.commit()
	add_child(road)


func _build_center_line() -> void:
	var frames := _road_frames()
	var positions: Array[Vector3] = frames["positions"]
	var rights: Array[Vector3] = frames["rights"]
	var count := positions.size()

	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in count - 1:
		var half := 0.09
		var lift := ROAD_LIFT + 0.01
		var p_l := positions[i] + rights[i] * half + Vector3.UP * lift
		var p_r := positions[i] - rights[i] * half + Vector3.UP * lift
		var q_l := positions[i + 1] + rights[i + 1] * half + Vector3.UP * lift
		var q_r := positions[i + 1] - rights[i + 1] * half + Vector3.UP * lift
		st.add_vertex(p_l)
		st.add_vertex(q_l)
		st.add_vertex(p_r)
		st.add_vertex(p_r)
		st.add_vertex(q_l)
		st.add_vertex(q_r)
	st.generate_normals()
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.85, 0.72, 0.15)
	mat.roughness = 0.8
	st.set_material(mat)
	var line := MeshInstance3D.new()
	line.mesh = st.commit()
	add_child(line)


func _build_trees() -> void:
	var baked := track.get_baked_points()
	var trunk_mesh := CylinderMesh.new()
	trunk_mesh.top_radius = 0.14
	trunk_mesh.bottom_radius = 0.2
	trunk_mesh.height = 2.2
	var trunk_mat := StandardMaterial3D.new()
	trunk_mat.albedo_color = Color(0.35, 0.24, 0.14)
	trunk_mat.roughness = 1.0
	trunk_mesh.material = trunk_mat

	var leaf_mesh := SphereMesh.new()
	leaf_mesh.radius = 1.4
	leaf_mesh.height = 3.2
	var leaf_mat := StandardMaterial3D.new()
	leaf_mat.albedo_color = Color(0.20, 0.38, 0.16)
	leaf_mat.roughness = 1.0
	leaf_mesh.material = leaf_mat

	var rng := RandomNumberGenerator.new()
	rng.seed = 20260101
	var side_flips := 0.0
	for i in TREE_COUNT:
		var t := float(i) / float(TREE_COUNT) * loop_len
		var idx := clampi(int(t / track.bake_interval), 0, baked.size() - 2)
		var tangent := (baked[idx + 1] - baked[idx]).normalized()
		var right := Vector3(tangent.z, 0.0, -tangent.x)
		side_flips += 0.61803
		var side := signf(sin(side_flips * TAU))
		var offset := side * (5.0 + rng.randf() * 14.0)
		var base := baked[idx] + right * offset
		var jitter := Vector3(rng.randf_range(-1.5, 1.5), 0.0,
				rng.randf_range(-1.5, 1.5))

		var trunk := MeshInstance3D.new()
		trunk.mesh = trunk_mesh
		trunk.position = base + jitter + Vector3.UP * 1.1
		add_child(trunk)

		var leaf := MeshInstance3D.new()
		leaf.mesh = leaf_mesh
		leaf.position = trunk.position + Vector3.UP * 2.6
		leaf.scale = Vector3.ONE * rng.randf_range(0.85, 1.25)
		add_child(leaf)


func _build_rider() -> void:
	rider_root = Node3D.new()
	rider_root.name = "RiderRoot"
	add_child(rider_root)

	var packed := load(RIDER_SCENE) as PackedScene
	if packed == null:
		push_error("rider.glb manquant : lancez blender/build_rider.py")
		return

	rider_rig = RiderRig.new()
	rider_rig.name = "RiderRig"
	rider_rig.add_child(packed.instantiate())
	rider_root.add_child(rider_rig)

	var curve_start := track.sample_baked(0.0, true)
	rider_root.global_position = curve_start + Vector3.UP * ROAD_LIFT


func _build_camera() -> void:
	camera = Camera3D.new()
	camera.fov = 62.0
	camera.position = Vector3(0.0, 2.4, -6.0)
	add_child(camera)
	camera.look_at(Vector3(0.0, 1.0, 0.0))
	camera.current = true


func _update_camera(delta: float, pos: Vector3, forward: Vector3) -> void:
	var target_pos: Vector3
	var look_target: Vector3
	if camera_chase:
		target_pos = pos - forward * 6.0 + Vector3.UP * 2.4
		look_target = pos + Vector3.UP * 1.0
	else:
		target_pos = pos - forward * 14.0 + Vector3.UP * 26.0
		look_target = pos + Vector3.UP * 0.5
	var k := 1.0 - exp(-5.0 * delta)
	_cam_pos = _cam_pos.lerp(target_pos, k) if _cam_pos != Vector3.ZERO \
			else target_pos
	camera.global_position = _cam_pos
	camera.look_at(look_target)


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------

func _build_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)

	var panel := PanelContainer.new()
	panel.position = Vector2(24.0, 24.0)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.08, 0.09, 0.12, 0.78)
	style.set_corner_radius_all(10)
	style.content_margin_left = 14.0
	style.content_margin_right = 14.0
	style.content_margin_top = 10.0
	style.content_margin_bottom = 10.0
	panel.add_theme_stylebox_override("panel", style)
	layer.add_child(panel)

	hud_data = Label.new()
	hud_data.add_theme_font_size_override("font_size", 22)
	hud_data.add_theme_color_override("font_color", Color(0.95, 0.95, 0.97))
	panel.add_child(hud_data)

	hud_help = Label.new()
	hud_help.text = "Flèches Haut/Bas : puissance   ·   F : caméra   ·   Échap : quitter"
	hud_help.add_theme_font_size_override("font_size", 16)
	hud_help.add_theme_color_override("font_color", Color(1, 1, 1, 0.75))
	hud_help.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	hud_help.position.y -= 46.0
	hud_help.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	layer.add_child(hud_help)


func _update_hud(speed: float, cadence: float, _offset: float) -> void:
	var kmh := speed * 3.6
	var km := distance_m / 1000.0
	hud_data.text = "Puissance  %3d W\nVitesse    %5.1f km/h\nCadence    %3.0f tr/min\nDistance   %6.2f km\nPente      0.0 %%" \
			% [int(power_w), kmh, cadence, km]
