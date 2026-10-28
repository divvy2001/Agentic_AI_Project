extends CharacterBody2D
class_name Player

signal health_changed(new_health:int)
signal died()

@export var speed:float = 180.0
@export var jump_velocity:float = 350.0
@export var gravity:float = 900.0
@export var punch_damage:int = 10
@export var punch_cooldown:float = 0.6 # seconds between punches
@export var punch_knockback:float = 200.0
@export var punch_range:float = 40.0 # fallback range if PunchArea missing
@export var max_health:int = 100

@export var punch_duration_fallback:float = 0.25

var health:int
var facing:int = 1 # 1 = right, -1 = left

var _can_punch:bool = true
var _is_punching:bool = false
var _punch_timer:float = 0.0

@onready var sprite:Sprite2D = $Sprite2D
@onready var animation_player:AnimationPlayer = $AnimationPlayer
@onready var punch_area:Area2D = $PunchArea

func _ready() -> void:
    health = max_health
    if punch_area:
        punch_area.monitoring = false
        punch_area.body_entered.connect(Callable(self, "_on_punch_area_body_entered"))

func _physics_process(delta: float) -> void:
    if get_tree().paused:
        return

    # gravity
    if not is_on_floor():
        velocity.y += gravity * delta
    else:
        if velocity.y > 0:
            velocity.y = 0

    var dir = 0
    if Input.is_action_pressed("ui_left"):
        dir -= 1
    if Input.is_action_pressed("ui_right"):
        dir += 1

    if dir != 0:
        velocity.x = dir * speed
        facing = dir
        if dir < 0:
            sprite.flip_h = true
            print("MOVE LEFT")
        else:
            sprite.flip_h = false
            print("MOVE RIGHT")
    else:
        velocity.x = lerp(velocity.x, 0.0, 0.2)

    # jumping
    if Input.is_action_just_pressed("ui_up") and is_on_floor():
        velocity.y = -jump_velocity
        print("JUMP")

    # punching
    if Input.is_action_just_pressed("ui_attack") and _can_punch and not _is_punching:
        _do_punch()

    # update punch timer
    if not _can_punch:
        _punch_timer -= delta
        if _punch_timer <= 0:
            _can_punch = true

    # apply movement (CharacterBody2D uses its built-in velocity property)
    move_and_slide()

    # animations (if provided by designer)
    if _is_punching:
        if animation_player and animation_player.has_animation("punch"):
            if not animation_player.is_playing():
                animation_player.play("punch")
    elif not is_on_floor():
        if animation_player and animation_player.has_animation("jump"):
            animation_player.play("jump")
    elif abs(velocity.x) > 10:
        if animation_player and animation_player.has_animation("walk"):
            animation_player.play("walk")
    else:
        if animation_player and animation_player.has_animation("idle"):
            animation_player.play("idle")

func _do_punch() -> void:
    _can_punch = false
    _is_punching = true
    _punch_timer = punch_cooldown
    print("PUNCH")

    var duration = punch_duration_fallback
    if animation_player and animation_player.has_animation("punch"):
        duration = max(duration, animation_player.get_animation("punch").length)
        animation_player.play("punch")

    if punch_area:
        punch_area.monitoring = true
        await get_tree().create_timer(duration).timeout
        if punch_area:
            punch_area.monitoring = false

    await get_tree().create_timer(duration).timeout
    _is_punching = false

func _on_punch_area_body_entered(body: Node) -> void:
    if body == self:
        return
    if not _is_punching:
        return
    if body.has_method("take_damage"):
        var kb_dir = (body.global_position.x - global_position.x)
        var kb_sign = 1 if kb_dir >= 0 else -1
        var knockback = Vector2(kb_sign * punch_knockback, -50)
        body.take_damage(punch_damage, knockback)

func take_damage(amount: int, knockback: Vector2) -> void:
    health = max(0, health - amount)
    emit_signal("health_changed", health)
    velocity += knockback
    if animation_player and animation_player.has_animation("hit"):
        animation_player.play("hit")
    else:
        var prev = sprite.modulate
        sprite.modulate = Color(1,0.6,0.6)
        await get_tree().create_timer(0.15).timeout
        sprite.modulate = prev
    if health <= 0:
        emit_signal("died")

func reset(pos: Vector2) -> void:
    health = max_health
    emit_signal("health_changed", health)
    global_position = pos
    velocity = Vector2.ZERO
    _can_punch = true
    _is_punching = false
    if punch_area:
        punch_area.monitoring = false
