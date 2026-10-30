extends Node2D

class_name Player

signal fell
signal passed_platform(platform)

@export var speed: float = 120.0
@export var gravity_strength: float = 800.0
@export var size: Vector2 = Vector2(32,32)

var gravity_dir: int = 1 # 1 = down, -1 = up
var velocity: Vector2 = Vector2.ZERO
var on_platform: bool = false
var current_platform = null
var start_position: Vector2 = Vector2.ZERO

const SPRITE_PATH := "res://assets/character_sprite.png"

func _ready() -> void:
	start_position = position
	# create a Sprite2D
	var sp := Sprite2D.new()
	sp.texture = load(SPRITE_PATH)
	sp.centered = true
	if sp.texture != null:
		sp.scale = Vector2(size.x / sp.texture.get_width(), size.y / sp.texture.get_height())
	add_child(sp)
	set_physics_process(true)

func _physics_process(delta: float) -> void:
	if not get_parent().playing:
		return
	# horizontal constant movement to the right
	position.x += speed * delta

	# vertical velocity due to gravity
	velocity.y += gravity_dir * gravity_strength * delta
	position.y += velocity.y * delta

	# Collision detection (manual snap to platform)
	var gm := get_parent()
	on_platform = false
	current_platform = null
	for plat in gm.platforms:
		var r: Rect2 = plat.get_rect()
		# check horizontal overlap
		var px_left := position.x - size.x/2
		var px_right := position.x + size.x/2
		var overlap_h := (px_right > r.position.x) and (px_left < r.position.x + r.size.x)
		if overlap_h:
			if gravity_dir == 1:
				# falling down: check if player's bottom is touching top of platform (allow small tolerance)
				var player_bottom := position.y + size.y/2
				var plat_top := r.position.y
				if player_bottom >= plat_top - 2 and player_bottom <= plat_top + 50 and velocity.y >= 0:
					# snap to platform top
					position.y = plat_top - size.y/2
					velocity.y = 0
					on_platform = true
					current_platform = plat
					break
			else:
				# gravity up: check if player's top touches bottom of ceiling platform
				var player_top := position.y - size.y/2
				var plat_bottom := r.position.y + r.size.y
				if player_top <= plat_bottom + 2 and player_top >= plat_bottom - 50 and velocity.y <= 0:
					position.y = plat_bottom + size.y/2
					velocity.y = 0
					on_platform = true
					current_platform = plat
					break

	# Check passing platform for scoring
	if current_platform != null:
		if position.x > current_platform.get_right_edge() and not current_platform.scored:
			emit_signal("passed_platform", current_platform)

	# Check fall off screen
	var viewport_size := get_viewport_rect().size
	if position.y - size.y/2 > viewport_size.y or position.y + size.y/2 < 0:
		# Fell off screen
		emit_signal("fell")

func flip_gravity() -> void:
	gravity_dir *= -1
	# smooth rotate
	var target := 0.0
	if gravity_dir == -1:
		target = 180.0
	else:
		target = 0.0
	get_tree().create_tween().tween_property(self, "rotation_degrees", target, 0.15)

func reset() -> void:
	position = start_position
	rotation_degrees = 0
	gravity_dir = 1
	velocity = Vector2.ZERO
	on_platform = false
	current_platform = null
	set_physics_process(true)
