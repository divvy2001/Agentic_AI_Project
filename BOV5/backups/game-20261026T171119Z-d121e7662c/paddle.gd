extends Area2D
class_name Paddle

@export var speed: float = 400.0

func _ready() -> void:
    # Ensure input actions exist (main also does this, but safe to have)
    if not InputMap.has_action("move_left"):
        InputMap.add_action("move_left")
    if not InputMap.has_action("move_right"):
        InputMap.add_action("move_right")

func _process(delta: float) -> void:
    var dir = 0
    if Input.is_action_pressed("move_left"):
        dir -= 1
    if Input.is_action_pressed("move_right"):
        dir += 1
    if dir != 0:
        position.x += dir * speed * delta
        # Clamp to viewport width (800) keeping sprite centered
        position.x = clamp(position.x, 64, 800 - 64)

func is_ball() -> bool:
    return false
