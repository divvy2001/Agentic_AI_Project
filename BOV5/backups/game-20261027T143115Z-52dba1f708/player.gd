extends CharacterBody2D
class_name Player

@export var speed: float = 220.0
@export var jump_force: float = -420.0
@export var max_health: int = 100

var health: int = 100
var facing: int = 1 # 1 = right, -1 = left
var ui = null
var game_over: bool = false

@onready var sprite: Sprite2D = Sprite2D.new()

func _init() -> void:
    # create sprite
    pass

func _ready() -> void:
    # Setup sprite
    add_child(sprite)
    var tex = load("res://assets/red_belt_fighter.png")
    if tex:
        sprite.texture = tex
        sprite.centered = true
        sprite.offset = Vector2.ZERO
    position = Vector2(200, 420)
    health = max_health
    set_physics_process(true)

func apply_damage(amount: int, knockback: Vector2) -> void:
    health = max(0, health - amount)
    # Apply knockback velocity
    velocity.x = knockback.x
    velocity.y = knockback.y
    # Flash white
    sprite.modulate = Color(1,1,1)
    await get_tree().create_timer(0.12).timeout
    sprite.modulate = Color(1,1,1,1)
    if ui:
        ui.on_health_changed("player", health)

func _physics_process(delta: float) -> void:
    if ui and ui.game_over:
        return
    var input_left = Input.is_action_pressed("ui_left")
    var input_right = Input.is_action_pressed("ui_right")
    var move_dir = 0
    if input_left:
        move_dir -= 1
    if input_right:
        move_dir += 1
    if move_dir < 0:
        facing = -1
    elif move_dir > 0:
        facing = 1
    if move_dir != 0:
        velocity.x = move_dir * speed
        if move_dir < 0:
            print("MOVE LEFT")
        else:
            print("MOVE RIGHT")
    else:
        velocity.x = 0
    # gravity
    if not is_on_floor():
        velocity.y += 20
    # jump
    if Input.is_action_just_pressed("ui_up") and is_on_floor():
        velocity.y = jump_force
        print("JUMP")
    # punch
    if Input.is_action_just_pressed("ui_accept"):
        _do_punch()
    move_and_slide()
    # Bounce off screen edges
    var margin = 32
    var screen_w = 800
    if position.x < margin:
        position.x = margin
        velocity.x = -velocity.x
    elif position.x > screen_w - margin:
        position.x = screen_w - margin
        velocity.x = -velocity.x

func _do_punch() -> void:
    print("PUNCH")
    # tween lunge forward and back - simple velocity impulse
    var orig_x = position.x
    var lunge = 20 * facing
    position.x += lunge
    await get_tree().create_timer(0.08).timeout
    position.x = orig_x
    # spawn hitbox (script instance)
    var hb = preload("res://punch_hitbox.gd").new()
    hb.attacker = self
    hb.damage = 10
    hb.position = position + Vector2(30 * facing, -10)
    get_parent().add_child(hb)

func reset(to_pos: Vector2) -> void:
    position = to_pos
    health = max_health
    velocity = Vector2.ZERO
    if ui:
        ui.on_health_changed("player", health)
