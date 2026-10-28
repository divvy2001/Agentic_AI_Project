extends Node2D

class_name Ball

signal bounced
signal missed

@export var radius:float = 10.0
@export var speed:float = 300.0
var velocity:Vector2 = Vector2.ZERO
var active:bool = true
var screen_size:Vector2 = Vector2.ZERO
var paddle:Node = null

func _ready() -> void:
    set_physics_process(true)
    queue_redraw()

func _draw() -> void:
    draw_circle(Vector2.ZERO, radius, Color(0.9,0.2,0.2))

func _physics_process(delta: float) -> void:
    if not active:
        return
    position += velocity * delta
    # wall collisions
    if screen_size != Vector2.ZERO:
        # left wall
        if position.x - radius < 0:
            position.x = radius
            velocity.x = abs(velocity.x)
        # right wall
        if position.x + radius > screen_size.x:
            position.x = screen_size.x - radius
            velocity.x = -abs(velocity.x)
        # top wall
        if position.y - radius < 0:
            position.y = radius
            velocity.y = abs(velocity.y)
    # paddle collision
    if paddle != null:
        var paddle_pos:Vector2 = paddle.position
        var paddle_size:Vector2 = paddle.size
        var rect_min = paddle_pos - paddle_size/2
        var rect_max = paddle_pos + paddle_size/2
        # closest point on rect to circle center
        var closest = Vector2(clamp(position.x, rect_min.x, rect_max.x), clamp(position.y, rect_min.y, rect_max.y))
        var d = position.distance_to(closest)
        if d <= radius and velocity.y > 0:
            # collided from above
            position.y = rect_min.y - radius
            # invert y
            velocity.y = -abs(velocity.y)
            # add spin from paddle horizontal movement
            var spin = 0.0
            if "velocity" in paddle:
                spin = paddle.velocity.x * 0.2
            velocity.x += spin
            # normalize to maintain speed
            if velocity.length() == 0:
                velocity = Vector2(0, -1) * speed
            else:
                velocity = velocity.normalized() * speed
            emit_signal("bounced")
            # call paddle squash if available
            if "squash" in paddle:
                paddle.squash()
    # missed check: ball below paddle bottom
    if paddle != null:
        var paddle_bottom = paddle.position.y + paddle.size.y/2
        if position.y - radius > paddle_bottom:
            active = false
            velocity = Vector2.ZERO
            emit_signal("missed")
    queue_redraw()

func reset(pos:Vector2) -> void:
    position = pos
    active = true
    # initial velocity mostly upwards
    velocity = Vector2(0.5, -0.9).normalized() * speed
    queue_redraw()

func stop() -> void:
    active = false
    velocity = Vector2.ZERO
    queue_redraw()
