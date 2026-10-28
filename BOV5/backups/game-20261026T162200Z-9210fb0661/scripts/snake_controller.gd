extends Node2D
class_name SnakeController

signal ate_orb
signal died

const TILE_SIZE: int = 32

var game_manager: Node = null
var segments: Array = [] # Array of Vector2 grid positions, head at index 0
var segment_nodes: Array = []
var direction: Vector2 = Vector2.RIGHT
var move_timer: Timer
var speed_level: int = 1
var move_interval: float = 0.18
var pending_grow: int = 0

func _init():
    pass

func setup(gm: Node) -> void:
    game_manager = gm
    # create timer
    move_timer = Timer.new()
    move_timer.one_shot = false
    move_timer.wait_time = move_interval
    add_child(move_timer)
    move_timer.connect("timeout", Callable(self, "_on_move_timer"))
    move_timer.start()
    # initial snake: 3 segments in center
    segments.clear()
    segment_nodes.clear()
    var start = Vector2(5,5)
    segments.append(start)
    segments.append(start - Vector2(1,0))
    segments.append(start - Vector2(2,0))

    # visual nodes: simple ColorRect style via Sprite2D created here
    _rebuild_visuals()

func _rebuild_visuals() -> void:
    for n in segment_nodes:
        if is_instance_valid(n):
            n.queue_free()
    segment_nodes.clear()
    for i in range(segments.size()):
        var s = Sprite2D.new()
        s.texture = null
        s.modulate = Color(0.3,1.0,0.3)
        s.centered = true
        s.scale = Vector2(0.9,0.9)
        add_child(s)
        segment_nodes.append(s)
    _update_visuals()

func _update_visuals() -> void:
    for i in range(segments.size()):
        var cell = segments[i]
        var pos = cell * TILE_SIZE + Vector2(TILE_SIZE/2, TILE_SIZE/2)
        var node = segment_nodes[i]
        node.position = pos
        node.z_index = 10 - i

func set_speed_level(level: int) -> void:
    if level != speed_level:
        speed_level = level
        # adjust interval
        move_interval = max(0.04, 0.18 - (speed_level - 1) * 0.02)
        if move_timer:
            move_timer.wait_time = move_interval

func set_direction(dir: Vector2) -> void:
    # avoid reversing
    if dir + direction == Vector2.ZERO:
        return
    direction = dir

func _on_move_timer() -> void:
    # read input for direction (keyboard support here for simplicity)
    if Input.is_action_just_pressed("move_up"):
        set_direction(Vector2(0,-1))
    elif Input.is_action_just_pressed("move_down"):
        set_direction(Vector2(0,1))
    elif Input.is_action_just_pressed("move_left"):
        set_direction(Vector2(-1,0))
    elif Input.is_action_just_pressed("move_right"):
        set_direction(Vector2(1,0))

    var new_head = segments[0] + direction
    # collision with walls
    if game_manager and game_manager.is_cell_blocked(new_head):
        emit_signal("died", "wall")
        game_manager.on_snake_death("wall")
        return
    # collision with self
    for i in range(1, segments.size()):
        if segments[i] == new_head:
            emit_signal("died", "self")
            game_manager.on_snake_death("self")
            return
    # move body
    segments.insert(0, new_head)
    if pending_grow > 0:
        pending_grow -= 1
    else:
        segments.pop_back()
    _update_visuals()

    # check orb
    if game_manager and game_manager.orb_manager and game_manager.orb_manager.consume_orb_at(new_head):
        pending_grow += 1
        emit_signal("ate_orb")
        if game_manager:
            game_manager.register_orb_eaten()

func is_occupying_cell(cell: Vector2) -> bool:
    for c in segments:
        if c == cell:
            return true
    return false

func grow(n: int=1) -> void:
    pending_grow += n

func reset() -> void:
    # reset to initial
    segments.clear()
    segments.append(Vector2(5,5))
    segments.append(Vector2(4,5))
    segments.append(Vector2(3,5))
    pending_grow = 0
    direction = Vector2(1,0)
    set_speed_level(1)
    _rebuild_visuals()

func _physics_process(delta: float) -> void:
    # slight wobble for body segments (visual only)
    for i in range(1, segment_nodes.size()):
        var node = segment_nodes[i]
        var wobble = sin(OS.get_ticks_msec() / 200.0 + i) * 2.0
        node.position.y += wobble
