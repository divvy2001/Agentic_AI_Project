extends Node2D
class_name Crumb

var tile := Vector2.ZERO
var radius := 4
var alive := true

# inner sparkle class to animate a brief expanding circle
class Sparkle:
	extends Node2D
	var t := 0.0
	var radius := 4.0
	func _ready() -> void:
		set_process(true)
	func _process(delta: float) -> void:
		t += delta
		queue_redraw()
		if t > 0.4:
			queue_free()
	func _draw() -> void:
		var alpha = clamp(1.0 - t / 0.4, 0.0, 1.0)
		var r = radius + t * 40
		draw_circle(Vector2.ZERO, r, Color(1,1,0,alpha))

func _draw() -> void:
	if alive:
		draw_circle(Vector2.ZERO, radius, Color(1,0.9,0))

func collect() -> void:
	if not alive:
		return
	alive = false
	queue_redraw()
	_spawn_sparkle()
	queue_free()

func _spawn_sparkle() -> void:
	var s = Sparkle.new()
	add_child(s)
	s.position = position
