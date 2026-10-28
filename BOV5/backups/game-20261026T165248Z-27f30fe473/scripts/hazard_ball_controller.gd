extends Node2D
class_name HazardBallController

@export var speed: float = 120.0
var velocity: Vector2 = Vector2.ZERO
var bounds: Rect2 = Rect2(0,0,1280,720)

func _ready() -> void:
    if velocity == Vector2.ZERO:
        velocity = Vector2(randf()*2-1, randf()*2-1).normalized() * speed

func _physics_process(delta: float) -> void:
    position += velocity * delta
    # bounce on bounds
    if position.x < bounds.position.x:
        position.x = bounds.position.x
        velocity.x = -velocity.x
    elif position.x > bounds.position.x + bounds.size.x:
        position.x = bounds.position.x + bounds.size.x
        velocity.x = -velocity.x
    if position.y < bounds.position.y:
        position.y = bounds.position.y
        velocity.y = -velocity.y
    elif position.y > bounds.position.y + bounds.size.y:
        position.y = bounds.position.y + bounds.size.y
        velocity.y = -velocity.y
