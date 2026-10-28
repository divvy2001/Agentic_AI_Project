# LandingPad: owns pad geometry and helpers
class_name LandingPad
extends Node2D

@export var width: float = 200.0
@export var height: float = 20.0

func _ready() -> void:
    queue_redraw()

func get_top_y() -> float:
    # top edge y coordinate in global space
    return global_position.y - (height * 0.5)

func contains_x(x: float) -> bool:
    var left: float = global_position.x - (width * 0.5)
    var right: float = global_position.x + (width * 0.5)
    return x >= left and x <= right

func _draw() -> void:
    var rect: Rect2 = Rect2(Vector2(-width * 0.5, -height * 0.5), Vector2(width, height))
    draw_rect(rect, Color(0.2, 0.6, 0.2))

func _notification(what):
    if what == NOTIFICATION_ENTER_TREE:
        queue_redraw()
