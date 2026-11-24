extends SceneTree

## Test de parite : la cinematique GDScript (scripts/rider_rig.gd) doit
## reproduire exactement rouelib/rider.py (valeurs d'or générées depuis
## le code Python original).
## Execution :
##   godot --headless --path godot -s tests/kinematics_test.gd

const TOLERANCE := 1e-4

const GOLDEN := {
	"0_L": [69.02460988578838, -106.44419186370573],
	"0_R": [26.123303165448878, -32.68179226728318],
	"45_L": [70.93740521720444, -91.89968797641713],
	"45_R": [28.939523088288876, -53.71864608222462],
	"90_L": [57.78399058883678, -66.43363853647092],
	"90_R": [38.79508278209735, -80.86331964742814],
	"135_L": [38.405568108531575, -40.34338917139765],
	"135_R": [53.81459227268924, -101.74622079934855],
	"180_L": [26.123303165448878, -32.68179226728318],
	"180_R": [69.0246098857884, -106.44419186370574],
	"225_L": [28.939523088288876, -53.71864608222462],
	"225_R": [70.93740521720444, -91.89968797641713],
	"270_L": [38.79508278209735, -80.86331964742814],
	"270_R": [57.78399058883678, -66.43363853647092],
	"315_L": [53.81459227268924, -101.74622079934855],
	"315_R": [38.405568108531575, -40.34338917139765],
}


func _initialize() -> void:
	var failures := 0
	var checks := 0
	for key in GOLDEN:
		var parts: PackedStringArray = String(key).split("_")
		var crank := float(parts[0])
		var phase := 0.0
		if parts[1] == "R":
			phase = 180.0
		var pose := RiderRig.leg_pose(crank, phase)
		var expected: Array = GOLDEN[key]
		var ok := absf(pose["thigh_z"] - expected[0]) <= TOLERANCE \
				and absf(pose["knee_z"] - expected[1]) <= TOLERANCE
		checks += 1
		if not ok:
			failures += 1
			print("ECHEC crank=%s : obtenu (%f, %f), attendu (%f, %f)" % [
					key, pose["thigh_z"], pose["knee_z"],
					expected[0], expected[1]])

	# Le modele physique doit tenir ses equilibres simples.
	var model := SpeedModel.new()
	var v := model.update(1.0, 0.0, 0.0)
	if v > 0.0:
		failures += 1
		print("ECHEC : vitesse %f sans puissance" % v)
	var v2: float = model.update(1.0, 200.0, 0.0)
	if v2 <= 0.0:
		failures += 1
		print("ECHEC : vitesse nulle avec 200 W")
	var v3: float = model.update(10.0, 200.0, 0.0)
	if v3 <= v2:
		failures += 1
		print("ECHEC : la vitesse n'accelere pas")
	checks += 3

	if failures == 0:
		print("KINEMATICS_TEST OK : %d/%d" % [checks, checks])
		quit(0)
	else:
		print("KINEMATICS_TEST ECHEC : %d/%d" % [checks - failures, checks])
		quit(1)
