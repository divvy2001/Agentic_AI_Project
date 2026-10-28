extends Node2D
class_name Mouse

signal ate_crumb(tile)
signal caught()

const TILE_SIZE := 32
const MOVE_SPEED := 6.0 # tiles per second

var maze: Maze = null
var tile: Vector2 = Vector2.ZERO
var target_tile: Vector2 = Vector2.ZERO
var direction: Vector2 = Vector2.ZERO
var intended: Vector2 = Vector2.ZERO
var moving: bool = false
var progress: float = 0.0
var active: bool = true

func setup(_maze, start_tile: Vector2) -> void:
    maze = _maze
    tile = start_tile
    target_tile = tile
    position = maze.tile_to_pos(tile)
    direction = Vector2.ZERO
    intended = Vector2.ZERO
    moving = false
    progress = 0.0
    active = true
    scale = Vector2.ONE

func set_intended_direction(d: Vector2) -> void:
    intended = d

func set_active(a: bool) -> void:
    active = a

func _process(delta: float) -> void:
    if not active:
        return
    if not is_inside_tree():
        return

    # decide direction if not moving
    if not moving:
        if intended != Vector2.ZERO and maze.is_open(tile + intended):
            direction = intended
        elif direction != Vector2.ZERO and maze.is_open(tile + direction):
            # continue in same direction
            pass
        else:
            direction = Vector2.ZERO

        if direction != Vector2.ZERO and maze.is_open(tile + direction):
            moving = true
            target_tile = tile + direction
            progress = 0.0
            return

    # if moving, advance along the tile
    if moving:
        var move_time := 1.0 / MOVE_SPEED
        progress += delta / move_time
        if progress >= 1.0:
            # Arrived at target
            tile = target_tile
            position = maze.tile_to_pos(tile)
            moving = false
            progress = 0.0
            # check crumb
            if maze.eat_crumb(tile):
                emit_signal("ate_crumb", tile)
            # check collision with cats at tile
            var parent = get_parent()
            if parent:
                for c in parent.get_children():
                    if c is Cat and c.tile == tile:
                        emit_signal("caught")
            # attempt to immediately take intended turn
            if intended != Vector2.ZERO and maze.is_open(tile + intended):
                direction = intended
                moving = true
                target_tile = tile + direction
                progress = 0.0
        else:
            var a = maze.tile_to_pos(tile)
            var b = maze.tile_to_pos(target_tile)
            position = a.lerp(b, progress)
            # squash and stretch animation
            var s := 1.0 + 0.15 * sin(progress * PI)
            scale = Vector2(1.0 / s, s)
            # check collision during movement
            var parent = get_parent()
            if parent:
                for c in parent.get_children():
                    if c is Cat:
                        # approximate collision if near cat position
                        if position.distance_to(c.position) < 8:
                            emit_signal("caught")

func respawn(start_tile: Vector2) -> void:
    tile = start_tile
    target_tile = tile
    position = maze.tile_to_pos(tile)
    direction = Vector2.ZERO
    intended = Vector2.ZERO
    moving = false
    progress = 0.0
    active = true
    scale = Vector2.ONE

