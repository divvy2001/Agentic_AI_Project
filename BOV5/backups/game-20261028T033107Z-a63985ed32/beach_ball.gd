extends Node2D
class_name BeachBall

@export var radius: float = 16.0
@export var initial_speed: float = 220.0
var velocity: Vector2 = Vector2(150, -200)
var angular_velocity: float = 0.0
var active: bool = true
@onready var sprite: Sprite2D = get_node_or_null("Sprite2D") as Sprite2D

func _ready() -> void:
	# set sprite origin if available
	if sprite and sprite.texture:
		radius = max(8.0, sprite.texture.get_size().x * 0.5)

func _physics_process(delta: float) -> void:
	if not active:
		return
	# simple physics integration
	position += velocity * delta
	rotation += angular_velocity * delta
	# screen bounds
	var vp_size: Vector2 = get_viewport().get_visible_rect().size
	# left/right bounce
	if position.x - radius <= 0 and velocity.x < 0:
		position.x = radius
		velocity.x = -velocity.x
		angular_velocity = -angular_velocity * 0.8
		# preserve momentum
	elif position.x + radius >= vp_size.x and velocity.x > 0:
		position.x = vp_size.x - radius
		velocity.x = -velocity.x
		angular_velocity = -angular_velocity * 0.8
	# top bounce
	if position.y - radius <= 0 and velocity.y < 0:
		position.y = radius
		velocity.y = -velocity.y
		angular_velocity *= 0.9
	# collision with seal (manual detection)
	var gm = get_tree().get_current_scene()
	if gm and gm.has_node("Seal"):
		var seal = gm.get_node("Seal")
		# compute seal top (seal sprite is centered)
		var seal_sprite: Sprite2D = null
		if seal.has_node("Sprite2D"):
			seal_sprite = seal.get_node("Sprite2D")
		var seal_half_w = 32.0
		var seal_top_y = seal.position.y
		if seal_sprite and seal_sprite.texture:
			seal_half_w = seal_sprite.texture.get_size().x * 0.5
			seal_top_y = seal.position.y - (seal_sprite.texture.get_size().y * 0.5)
		# only collide when ball is moving downwards and crossing seal top
		if velocity.y > 0 and position.y + radius >= seal_top_y and position.y - radius < seal.position.y:
			# check horizontal overlap
			if abs(position.x - seal.position.x) <= (seal_half_w + radius):
				# perform bounce and score
				var seal_vel_x = 0.0
				if seal.has_method("get_velocity"):
					seal_vel_x = seal.get_velocity().x
				# adjust position to avoid sticking
				position.y = seal_top_y - radius - 1
				bounce_from_seal(seal_vel_x)
				if gm.has_method("increment_score"):
					gm.increment_score()
		# check fall past seal -> game over
		if position.y - radius > seal.position.y:
			# ball fell past seal
			if gm.has_method("game_over"):
				gm.game_over()
			# stop the ball
			stop()

func bounce_from_seal(seal_vel_x: float) -> void:
	# Called by Seal when the ball hits the seal's nose area.
	# Reflect vertical velocity and add influence from seal's horizontal velocity.
	if not active:
		return
	velocity.y = -abs(velocity.y) if velocity.y > 0 else -abs(velocity.y)
	velocity.y = -abs(velocity.y) if velocity.y >= 0 else velocity.y
	velocity.y = -abs(velocity.y)
	# give a minimum upward speed
	velocity.y = min(velocity.y, -150)
	# add seal horizontal momentum to ball's x velocity
	velocity.x += seal_vel_x * 0.5
	# limit speed
	if velocity.length() > 800:
		velocity = velocity.normalized() * 800
	# spin based on seal movement
	angular_velocity += seal_vel_x * 0.02

func stop() -> void:
	active = false
	velocity = Vector2.ZERO
	angular_velocity = 0.0

func reset_to_start() -> void:
	var vp_size: Vector2 = get_viewport().get_visible_rect().size
	position = Vector2(vp_size.x * 0.5 + 60, vp_size.y * 0.5 - 100)
	velocity = Vector2(initial_speed, -initial_speed)
	angular_velocity = 0.0
	active = true
