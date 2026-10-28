extends Node2D
class_name OrbManager

const TILE_SIZE: int = 32
var game_manager: Node = null
var orbs := {} # map "x,y" -> Dictionary {node, cell}

func setup(gm: Node) -> void:
    game_manager = gm

func spawn_orb() -> void:
    if not game_manager:
        return
    var cell: Vector2 = game_manager.get_random_free_cell()
    var key = "%d,%d" % [cell.x, cell.y]
    if orbs.has(key):
        return
    var s := Sprite2D.new()
    var tex_path := "res://game/assets/orb.png"
    if ResourceLoader.exists(tex_path):
        s.texture = load(tex_path)
    s.centered = true
    s.position = cell * TILE_SIZE + Vector2(TILE_SIZE/2, TILE_SIZE/2)
    add_child(s)
    orbs[key] = {"node": s, "cell": cell}

func has_orb_at(cell: Vector2) -> bool:
    return orbs.has("%d,%d" % [cell.x, cell.y])

func consume_orb_at(cell: Vector2) -> bool:
    var key = "%d,%d" % [cell.x, cell.y]
    if not orbs.has(key):
        return false
    var data = orbs[key]
    var node = data["node"]
    if is_instance_valid(node):
        node.queue_free()
    orbs.erase(key)
    # spawn particle effect if available
    var pe_path := "res://game/resources/particle_effects.tscn"
    if ResourceLoader.exists(pe_path):
        var pe_res = load(pe_path)
        if pe_res:
            var inst = pe_res.instantiate()
            add_child(inst)
            inst.global_position = cell * TILE_SIZE + Vector2(TILE_SIZE/2, TILE_SIZE/2)
            var t = Timer.new()
            t.one_shot = true
            t.wait_time = 1.0
            add_child(t)
            t.connect("timeout", Callable(inst, "queue_free"))
            t.start()
    # spawn another orb after short delay
    var t2 = Timer.new()
    t2.one_shot = true
    t2.wait_time = 0.5
    add_child(t2)
    t2.connect("timeout", Callable(self, "spawn_orb"))
    t2.start()
    return true

func reset() -> void:
    for key in orbs.keys():
        var data = orbs[key]
        var node = data["node"]
        if is_instance_valid(node):
            node.queue_free()
    orbs.clear()
