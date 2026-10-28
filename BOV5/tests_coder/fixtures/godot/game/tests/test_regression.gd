extends SceneTree

func _initialize() -> void:
    var packed: PackedScene = load("res://main.tscn")
    if packed == null:
        push_error("Scene could not load")
        quit(2)
        return
    var node: Node = packed.instantiate()
    root.add_child(node)
    for i in range(2):
        node.award_point()
    if node.score != 2 or node.phase != "PLAYING":
        push_error("T01 failed: score=" + str(node.score) + ", phase=" + node.phase)
        quit(1)
    else:
        quit(0)
