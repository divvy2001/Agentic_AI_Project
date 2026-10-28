extends Node2D
class_name SnakeController

signal moved_to(new_pos: Vector2i)
signal died()

const TILE_SIZE: int = 32

@export var initial_length: int = 3
@export var initial_pos: Vector2i = Vector2i(5,5)

var positions: Array = [] # Array of Vector2i
var direction: Vector2i = Vector2i(1,0)
var pending_direction: Vector2i = Vector2i(1,0)
var move_interval: float = 0.2
var _timer: Timer
var _tween: Tween
var _growing: bool = false

func _ready() -> void:
    _timer = Timer.new()
    _timer.wait_time = move_interval
    _timer.one_shot = false
    add_child(_timer)
    _timer.connect("timeout", Callable(self, "_on_move_tick"))

    _tween = Tween.new()
    add_child(_tween)

    _init_snake()

func _init_snake() -> void:
    positions.clear()
    for i in range(initial_length):
        positions.append(initial_pos - Vector2i(i,0))
    # Ensure visuals exist
    if not has_node("Head"):
        var head = Sprite2D.new()
        head.name = "Head"
        head.centered = true
        add_child(head)
    if not has_node("Body"):
        var body = Node2D.new()
        body.name = "Body"
        add_child(body)
    _rebuild_body_sprites()
    _sync_visuals_immediately()

func _rebuild_body_sprites() -> void:
    var body = get_node("Body") as Node2D
    for child in body.get_children():
        child.queue_free()
    for i in range(max(0, positions.size()-1)):
        var s = Sprite2D.new()
        s.centered = true
        body.add_child(s)

func _sync_visuals_immediately() -> void:
    var head = get_node("Head") as Sprite2D
    head.global_position = positions[0] * TILE_SIZE
    var body = get_node("Body") as Node2D
    for i in range(body.get_child_count()):
        var s = body.get_child(i) as Sprite2D
        var pos = positions[i+1]
        s.global_position = pos * TILE_SIZE

func start(p_move_interval: float) -> void:
    move_interval = p_move_interval
    if _timer:
        _timer.wait_time = move_interval
        _timer.start()

func stop() -> void:
    if _timer:
        _timer.stop()

func grow() -> void:
    _growing = true

func get_positions() -> Array:
    return positions.duplicate()

func _on_move_tick() -> void:
    var input = Input
    if input.is_action_pressed("move_up"):
        pending_direction = Vector2i(0,-1)
    elif input.is_action_pressed("move_down"):
        pending_direction = Vector2i(0,1)
    elif input.is_action_pressed("move_left"):
        pending_direction = Vector2i(-1,0)
    elif input.is_action_pressed("move_right"):
        pending_direction = Vector2i(1,0)
    # prevent reversing
    if pending_direction + direction != Vector2i(0,0):
        direction = pending_direction
    var new_head = positions[0] + direction
    positions.insert(0, new_head)
    if not _growing:
        positions.pop_back()
    else:
        _growing = false
        _rebuild_body_sprites()
    emit_signal("moved_to", positions[0])
    _animate_to_positions()
    # check self-collision
    for i in range(1, positions.size()):
        if positions[i] == positions[0]:
            emit_signal("died")
            stop()
            return

func _animate_to_positions() -> void:
    _tween.kill()
    var head = get_node("Head") as Sprite2D
    _tween.tween_property(head, "global_position", positions[0]*TILE_SIZE, move_interval)
    var body = get_node("Body") as Node2D
    for i in range(body.get_child_count()):
        var s = body.get_child(i) as Sprite2D
        var target = positions[i+1] * TILE_SIZE
        var wobble = Vector2.ZERO
        var ang = (OS.get_ticks_msec() / 200.0) + i
        wobble = Vector2(cos(ang), sin(ang)) * 4
        _tween.tween_property(s, "global_position", target + wobble, move_interval)
    _tween.play()

func reset_state() -> void:
    stop()
    _growing = false
    direction = Vector2i(1,0)
    pending_direction = Vector2i(1,0)
    _init_snake()

func _on_external_die() -> void:
    emit_signal("died")
    stop()
