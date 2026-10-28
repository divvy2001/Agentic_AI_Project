extends Area2D
class_name Seal

@export var speed: float = 320.0
var velocity: Vector2 = Vector2.ZERO
@onready var sprite: Sprite2D = get_node_or_null("Sprite2D") as Sprite2D
var half_width: float = 32.0

func _ready() -> void:
	# calculate half width from sprite texture if available
	if sprite and sprite.texture:
		half_width = sprite.texture.get_size().x * 0.5
	else:
		half_width = 32.0
	# connect body entered
	if not is_connected("body_entered", Callable(self, "_on_body_entered")):
		connect("body_entered", Callable(self, "_on_body_entered"))

func _physics_process(delta: float) -> void:
	var dir := 0
	if Input.is_action_pressed("move_left"):
		dir -= 1
	if Input.is_action_pressed("move_right"):
		dir += 1
	velocity.x = dir * speed
	# Print one line per press
	if Input.is_action_just_pressed("move_left"):
		print("MOVE LEFT")
	if Input.is_action_just_pressed("move_right"):
		print("MOVE RIGHT")
	# Apply movement
	position.x += velocity.x * delta
	# Clamp to screen edges
	var vp_size: Vector2 = get_viewport().get_visible_rect().size
	position.x = clamp(position.x, half_width, vp_size.x - half_width)

func get_velocity() -> Vector2:
	return velocity

func reset_to_start() -> void:
	var vp_size: Vector2 = get_viewport().get_visible_rect().size
	position = Vector2(vp_size.x * 0.5, vp_size.y - 60)
	velocity = Vector2.ZERO

func _on_body_entered(body: Node) -> void:
	# Called when the ball (RigidBody2D) enters the seal area
	if body and body.has_method("bounce_from_seal"):
		body.bounce_from_seal(velocity.x)
