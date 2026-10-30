extends Node2D

class_name Platform

@export var size: Vector2 = Vector2(200, 20)
@export var is_ceiling: bool = false
var scored: bool = false

func _ready() -> void:
	# Request a redraw and create collision shape
	queue_redraw()
	_create_collision()

func _draw() -> void:
	var col: Color
	if is_ceiling:
		col = Color8(150, 50, 50)
	else:
		col = Color8(50, 150, 50)
	draw_rect(Rect2(Vector2.ZERO, size), col)

func _create_collision() -> void:
	# Ensure a StaticBody2D with CollisionShape2D matches the drawn rect
	if not has_node("StaticBody2D"):
		var sb := StaticBody2D.new()
		sb.name = "StaticBody2D"
		add_child(sb)
		var shape := RectangleShape2D.new()
		shape.size = size
		var cs := CollisionShape2D.new()
		cs.shape = shape
		sb.add_child(cs)
		# position the collision shape to match the drawn rect (centered)
		cs.position = size/2

func reset() -> void:
	scored = false

func get_right_edge() -> float:
	return global_position.x + size.x

func get_rect() -> Rect2:
	return Rect2(global_position, size)
