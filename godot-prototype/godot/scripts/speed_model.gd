extends RefCounted
class_name SpeedModel

## Port GDScript de rouelib/physics.py (jalon 1 du prototype Godot).
## Integre la vitesse du cycliste a partir de sa puissance :
##   m*dv/dt = P_roue/v - 0.5*rho*CdA*v^2 - m*g*cos(theta)*Crr - m*g*sin(theta)

const RHO_AIR := 1.225
const G := 9.81
const MAX_SPEED_MS := 30.0

var weight_kg := 78.0
var bike_kg := 10.0
var cda := 0.40
var crr := 0.004
var drivetrain_loss := 0.03

var speed := 0.0


func reset() -> void:
	speed = 0.0


func total_mass() -> float:
	return weight_kg + bike_kg


func update(dt: float, power_w: float, grade: float) -> float:
	var mass := total_mass()
	var p_wheel := power_w * (1.0 - drivetrain_loss) if power_w > 0.0 else 0.0
	var theta := atan(grade)
	var a := 0.0

	if speed > 0.2:
		var drag := 0.5 * RHO_AIR * cda * speed * speed
		var roll := mass * G * cos(theta) * crr
		var accel_force := (p_wheel / speed) - drag - roll - mass * G * sin(theta)
		a = accel_force / mass
	else:
		var ref_speed := 0.6
		a = (p_wheel / ref_speed
				- mass * G * sin(theta)
				- mass * G * cos(theta) * crr) / mass
		if a < 0.0:
			a = 0.0

	speed = minf(MAX_SPEED_MS, maxf(0.0, speed + a * dt))
	return speed
