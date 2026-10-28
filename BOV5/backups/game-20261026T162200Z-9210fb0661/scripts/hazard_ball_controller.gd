extends Node2D
class_name HazardBallController

const TILE_SIZE: int = 32
var game_manager: Node = null
var velocity: Vector2 = Vector2.ZERO

func setup(gm: Node, initial_velocity: Vector2) -> void:
    game_manager = gm
    velocity = initial_velocity

func _physics_process(delta: float) -> void:
    if velocity == Vector2.ZERO:
        return
    global_position += velocity * delta
    # bounce against arena rect
    if not game_manager:
        return
    var rect = game_manager.arena_rect_pixels
    if global_position.x < rect.position.x + 4:
        global_position.x = rect.position.x + 4
        velocity.x = -velocity.x
    elif global_position.x > rect.position.x + rect.size.x - 4:
        global_position.x = rect.position.x + rect.size.x - 4
        velocity.x = -velocity.x
    if global_position.y < rect.position.y + 4:
        global_position.y = rect.position.y + 4
        velocity.y = -velocity.y
    elif global_position.y > rect.position.y + rect.size.y - 4:
        global_position.y = rect.position.y + rect.size.y - 4
        velocity.y = -velocity.y

    # check collision with snake head
    if game_manager and game_manager.snake_controller:
        var head_pos = game_manager.snake_controller.segments[0] * TILE_SIZE + Vector2(TILE_SIZE/2, TILE_SIZE/2)
        if head_pos.distance_to(global_position) < TILE_SIZE * 0.6:
            game_manager.on_snake_death("hazard")
