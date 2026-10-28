extends Area2D
class_name Ball

signal bounced
signal missed

@export var velocity: Vector2 = Vector2(0, 200)
@export var gravity: float = 300.0
@export var angular_velocity: float = 5.0

@@onready var sprite: Sprite2D = $Sprite2D

func _ready() -> void:
    # Connect to area entered to detect paddle collisions
    connect("area_entered", Callable(self, "_on_area_entered"))

func _physics_process(delta: float) -> void:
    # Apply gravity
    velocity.y += gravity * delta
    position += velocity * delta
    # Spin
    rotation += angular_velocity * delta

    var view_size = get_viewport_rect().size
    var r = 16
    # Wall collisions (left/right)
    if position.x < r:
        position.x = r
        velocity.x = abs(velocity.x)
    elif position.x > view_size.x - r:
        position.x = view_size.x - r
        velocity.x = -abs(velocity.x)
    # Top
    if position.y < r:
        position.y = r
        velocity.y = abs(velocity.y)
    # Missed (fell below screen)
    if position.y > view_size.y + 32:
        emit_signal("missed")
        queue_free()

func _on_area_entered(area: Area2D) -> void:
    if area.name == "Paddle":
        # Only bounce if moving downward
        if velocity.y > 0:
            # reflect upward
            velocity.y = -abs(velocity.y) * 0.9
            # Add sideways influence based on contact point
            var offset = position.x - area.global_position.x
            velocity.x += offset * 3.0
            # Slight spin change
            angular_velocity += offset * 0.01
            emit_signal("bounced")

func is_ball() -> bool:
    return true

func reset(pos: Vector2, vel: Vector2) -> void:
    position = pos
    velocity = vel
    rotation = 0
