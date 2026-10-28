extends Node
class_name OrbManager

const TILE_SIZE: int = 32

@export var orb_scene: PackedScene
var current_orb: Node = null
var arena_root: Node = null

func _ready() -> void:
    pass

func setup(p_arena_root: Node, p_orb_scene: PackedScene) -> void:
    arena_root = p_arena_root
    orb_scene = p_orb_scene
    spawn_one()

func spawn_one() -> void:
    if not arena_root or not orb_scene:
        return
    # choose random spawn point from arena's OrbSpawns
    var spawns = []
    if arena_root.has_node("OrbSpawns"):
        for child in arena_root.get_node("OrbSpawns").get_children():
            if child is Position2D:
                spawns.append(child.global_position)
    if spawns.empty():
        # fallback: center
        var pos = Vector2(arena_root.position)
    else:
        var pos = spawns[randi() % spawns.size()]
    if current_orb:
        current_orb.queue_free()
    current_orb = orb_scene.instantiate()
    current_orb.position = pos
    arena_root.add_child(current_orb)

func consume_at(grid_pos: Vector2i) -> bool:
    if not current_orb or not arena_root:
        return false
    var orb_global = current_orb.global_position
    var orb_grid = Vector2i(int(round(orb_global.x / TILE_SIZE)), int(round(orb_global.y / TILE_SIZE)))
    if orb_grid == grid_pos:
        current_orb.queue_free()
        current_orb = null
        spawn_one()
        return true
    return false

func clear_all() -> void:
    if current_orb:
        current_orb.queue_free()
        current_orb = null
