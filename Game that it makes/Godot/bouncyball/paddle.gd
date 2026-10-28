extends Node2D

class_name Paddle

@export var size:Vector2 = Vector2(120,18)
@export var speed:float = 480.0
var velocity:Vector2 = Vector2.ZERO
var screen_size:Vector2 = Vector2.ZERO

func _ready() -> void:
    set_process(false)
    set_physics_process(true)
    queue_redraw()

func _draw() -> void:
    var rect = Rect2(-size/2, size)
    draw_rect(rect, Color(0.2,0.6,0.9))

func _physics_process(delta: float) -> void:
    var new_vx:float = 0.0
    if Input.is_action_pressed("move_left"):
        new_vx -= speed
        if Input.is_action_just_pressed("move_left"):
            print("MOVE LEFT")
    if Input.is_action_pressed("move_right"):
        new_vx += speed
        if Input.is_action_just_pressed("move_right"):
            print("MOVE RIGHT")
    velocity.x = new_vx
    position.x += velocity.x * delta
    # clamp to screen edges so paddle doesn't go off-screen
    if screen_size != Vector2.ZERO:
        var halfw:float = size.x/2
        position.x = clamp(position.x, halfw, screen_size.x - halfw)
    queue_redraw()

func squash() -> void:
    # quick squash visual: briefly change scale then return
    scale = Vector2(1.05, 0.9)
    queue_redraw()
    await get_tree().create_timer(0.08).timeout
    scale = Vector2(1,1)
    queue_redraw()
