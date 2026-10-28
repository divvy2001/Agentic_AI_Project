# Lander: handles physics, input and rendering
class_name Lander
extends Node2D

signal touched_ground(pos: Vector2, vertical_speed: float, angle_deg: float)

@export var size: Vector2 = Vector2(24, 24)
var velocity: Vector2 = Vector2.ZERO
var thrusting: bool = false
var frozen: bool = false
var on_ground: bool = false
var pad: Node = null

const GRAVITY: float = 300.0
const THRUST_FORCE: float = 700.0
const ROTATION_SPEED_DEG: float = 120.0
const HORIZONTAL_DAMPING: float = 0.995

func _ready() -> void:
    set_physics_process(true)
    queue_redraw()

func set_pad(p: Node) -> void:
    pad = p

func reset(pos: Vector2) -> void:
    global_position = pos
    velocity = Vector2.ZERO
    rotation_degrees = 0.0
    thrusting = false
    frozen = false
    on_ground = false
    queue_redraw()

func freeze() -> void:
    frozen = true
    velocity = Vector2.ZERO
    thrusting = false
    queue_redraw()

func _physics_process(delta: float) -> void:
    if frozen:
        return

    # Input: rotation
    if Input.is_action_pressed("ui_left"):
        rotation_degrees -= ROTATION_SPEED_DEG * delta
        if Input.is_action_just_pressed("ui_left"):
            print("ROTATE LEFT")
    if Input.is_action_pressed("ui_right"):
        rotation_degrees += ROTATION_SPEED_DEG * delta
        if Input.is_action_just_pressed("ui_right"):
            print("ROTATE RIGHT")

    # Thrust
    if Input.is_action_pressed("ui_up"):
        # Direction: upwards relative to lander (rotation 0 = facing up)
        var dir: Vector2 = Vector2(0, -1).rotated(rotation)
        velocity += dir * THRUST_FORCE * delta
        if Input.is_action_just_pressed("ui_up"):
            print("THRUST")
        thrusting = true
    else:
        thrusting = false

    # Gravity
    velocity.y += GRAVITY * delta

    # Damping (simple air resistance)
    velocity.x *= HORIZONTAL_DAMPING

    # Integrate
    global_position += velocity * delta

    # Bounce on left/right edges
    var vw: float = get_viewport_rect().size.x
    var halfw: float = size.x * 0.5
    if global_position.x - halfw < 0.0:
        global_position.x = halfw
        velocity.x = -velocity.x * 0.8
    elif global_position.x + halfw > vw:
        global_position.x = vw - halfw
        velocity.x = -velocity.x * 0.8

    # Check ground contact
    if pad != null and not on_ground:
        var pad_top: float = pad.get_top_y()
        var bottom_y: float = global_position.y + (size.y * 0.5)
        if bottom_y >= pad_top:
            on_ground = true
            # report vertical speed (positive downward)
            var vertical_speed = velocity.y
            var angle_deg = fmod(abs(rotation_degrees), 360.0)
            # Normalize angle to 0..180
            if angle_deg > 180.0:
                angle_deg = 360.0 - angle_deg
            emit_signal("touched_ground", global_position, vertical_speed, angle_deg)

    queue_redraw()

func _draw() -> void:
    # Draw the lander as a triangle pointing up (centered)
    var h: float = size.y * 0.5
    var w: float = size.x * 0.5
    var points: PackedVector2Array = PackedVector2Array([
        Vector2(0, -h),
        Vector2(-w, h),
        Vector2(w, h)
    ])
    draw_polygon(points, [Color(0.9, 0.9, 0.9)])

    # Draw legs
    draw_line(Vector2(-w * 0.6, h * 0.8), Vector2(-w * 0.2, h * 0.3), Color(0.7, 0.7, 0.7), 2)
    draw_line(Vector2(w * 0.6, h * 0.8), Vector2(w * 0.2, h * 0.3), Color(0.7, 0.7, 0.7), 2)

    # Flame when thrusting: small triangle behind the lander
    if thrusting:
        var fpoints: PackedVector2Array = PackedVector2Array([
            Vector2(0, h + 6),
            Vector2(-6, h * 0.2),
            Vector2(6, h * 0.2)
        ])
        draw_polygon(fpoints, [Color(1.0, 0.4, 0.0)])

func _notification(what):
    if what == NOTIFICATION_EXIT_TREE:
        # Clean up if needed
        pass
