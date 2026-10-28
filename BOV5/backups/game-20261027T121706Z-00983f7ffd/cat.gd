extends Node2D
class_name Cat

const TILE_SIZE := 32
const MOVE_SPEED := 4.0 # tiles per second (slower than mouse)

var maze: Maze = null
var tile: Vector2 = Vector2.ZERO
var target_tile: Vector2 = Vector2.ZERO
var moving: bool = false
var direction: Vector2 = Vector2.ZERO
var progress: float = 0.0
var active: bool = true
var mouse_ref = null

func setup(_maze, start_tile: Vector2, _mouse: Mouse) -> void:
    maze = _maze
    tile = start_tile
    target_tile = tile
    position = maze.tile_to_pos(tile)
    mouse_ref = _mouse
    moving = false
    direction = Vector2.ZERO
    progress = 0.0
    active = true

func set_active(a: bool) -> void:
    active = a

func _process(delta: float) -> void:
    if not active:
        return
    if not is_inside_tree():
        return
    if not moving:
        # choose a direction: if at junction, pick neighbor minimizing distance to mouse
        var options: Array = []
        for d in [Vector2(1,0), Vector2(-1,0), Vector2(0,1), Vector2(0,-1)]:
            if maze.is_open(tile + d):
                options.append(d)
        if options.size() == 0:
            return
        # pick direction that reduces distance to mouse
        var best = options[0]
        var bestd = 1e9
        for o in options:
            var t = tile + o
            var dist = (t - mouse_ref.tile).length()
            if dist < bestd:
                bestd = dist
                best = o
        direction = best
        moving = true
        target_tile = tile + direction
        progress = 0.0
    else:
        var move_time := 1.0 / MOVE_SPEED
        progress += delta / move_time
        if progress >= 1.0:
            tile = target_tile
            position = maze.tile_to_pos(tile)
            moving = false
            progress = 0.0
            # check catch
            if mouse_ref != null and tile == mouse_ref.tile:
                var parent = get_parent()
                if parent and parent.has_method("_on_mouse_caught"):
                    parent._on_mouse_caught()
        else:
            var a = maze.tile_to_pos(tile)
            var b = maze.tile_to_pos(target_tile)
            position = a.lerp(b, progress)

func respawn(start_tile: Vector2) -> void:
    tile = start_tile
    position = maze.tile_to_pos(tile)
    target_tile = tile
    moving = false
    direction = Vector2.ZERO
    progress = 0.0
    active = true
