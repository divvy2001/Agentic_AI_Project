extends CharacterBody2D
class_name Rival

@export var speed: float = 160.0
@export var jump_force: float = -380.0
@export var max_health: int = 100

var health: int = 100
var facing: int = -1 # faces left initially
var ui = null
var target: Node = null
var punch_cooldown: float = 1.0
var _punch_timer: float = 0.0

@onready var sprite: Sprite2D = Sprite2D.new()

func _ready() -> void:
    add_child(sprite)
    var tex = load("res://assets/blue_belt_fighter.png")
    if tex:
        sprite.texture = tex
        sprite.centered = true
        sprite.offset = Vector2.ZERO
    health = max_health
    set_physics_process(true)

func apply_damage(amount: int, knockback: Vector2) -> void:
    health = max(0, health - amount)
    velocity.x = knockback.x
    velocity.y = knockback.y
    sprite.modulate = Color(1,1,1)
    await get_tree().create_timer(0.12).timeout
    sprite.modulate = Color(1,1,1,1)
    if ui:
        ui.on_health_changed("rival", health)

func _physics_process(delta: float) -> void:
    if ui and ui.game_over:
        return
    if not target:
        return
    var dir = sign(target.position.x - position.x)
    facing = dir
    # move toward player if far
    var dist = abs(target.position.x - position.x)
    if dist > 120:
        velocity.x = dir * speed
    else:
        velocity.x = 0
        # punch if close and cooldown elapsed
        _punch_timer -= delta
        if _punch_timer <= 0:
            _do_punch()
            _punch_timer = punch_cooldown
    # gravity
    if not is_on_floor():
        velocity.y += 20
    move_and_slide()

func _do_punch() -> void:
    print("RIVAL PUNCH")
    # lunge
    var orig_x = position.x
    var lunge = -16 * facing
    position.x += lunge
    await get_tree().create_timer(0.08).timeout
    position.x = orig_x
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
        ui.on_health_changed("rival", health)
