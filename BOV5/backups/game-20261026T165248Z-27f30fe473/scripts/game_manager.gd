extends Node2D
class_name GameManager

const TILE_SIZE: int = 32
const BASE_MOVE_INTERVAL: float = 0.2
const SPEED_STEP: float = 0.02
const WIN_SCORE: int = 100

@export var arena_scenes: Array[PackedScene] = []
@export var snake_scene: PackedScene
@export var orb_scene: PackedScene
@export var hazard_scene: PackedScene
@export var ui_scene: PackedScene
@export var particle_scene: PackedScene

var current_arena: Node = null
var arena_index: int = 0
var orb_manager: OrbManager = null
var snake: SnakeController = null
var ui: UIController = null
var hazards: Array = []

var score: int = 0
var orbs_eaten: int = 0
var speed_level: int = 0
var game_over: bool = false

func _ready() -> void:
    OS.window_title = "Neon Serpent"
    _setup_input()

    # preload/exported scenes should be filled in the editor or by the tscn ext_resources
    # instantiate UI
    if ui_scene:
        ui = ui_scene.instantiate() as UIController
        add_child(ui)
        ui.update_score(score)
        ui.update_speed(speed_level)

    # create orb manager
    orb_manager = OrbManager.new()
    add_child(orb_manager)

    _load_arena(arena_index)
    _start_play()

func _setup_input() -> void:
    var im = InputMap
    func add_binding(name, keycodes):
        if not InputMap.has_action(name):
            InputMap.add_action(name)
        for kc in keycodes:
            var ev = InputEventKey.new()
            ev.physical_keycode = kc
            InputMap.action_add_event(name, ev)
    # Movement: arrows and WASD
    add_binding("move_up", [KEY_UP, KEY_W])
    add_binding("move_down", [KEY_DOWN, KEY_S])
    add_binding("move_left", [KEY_LEFT, KEY_A])
    add_binding("move_right", [KEY_RIGHT, KEY_D])
    add_binding("restart", [KEY_R])
    add_binding("quit", [KEY_ESCAPE])

func _load_arena(index: int) -> void:
    if current_arena:
        current_arena.queue_free()
        current_arena = null
    if index < 0 or index >= arena_scenes.size():
        return
    current_arena = arena_scenes[index].instantiate()
    add_child(current_arena)

    # setup orb manager with orb scene
    orb_manager.setup(current_arena, orb_scene)

    # clear previous hazards and spawn new ones
    for h in hazards:
        if h and h.is_inside_tree():
            h.queue_free()
    hazards.clear()
    if current_arena.has_node("HazardSpawns"):
        for child in current_arena.get_node("HazardSpawns").get_children():
            if child is Position2D:
                var hb = hazard_scene.instantiate()
                hb.position = child.global_position
                # set bounds if possible
                if hb.has_method("set"):
                    hb.bounds = Rect2(0,0,1280,720)
                current_arena.add_child(hb)
                hazards.append(hb)

    # spawn snake
    if snake:
        snake.queue_free()
        snake = null
    if snake_scene:
        snake = snake_scene.instantiate() as SnakeController
        add_child(snake)
        snake.reset_state()
        snake.connect("moved_to", Callable(self, "_on_snake_moved"))
        snake.connect("died", Callable(self, "_on_snake_died"))

func _start_play() -> void:
    score = 0
    orbs_eaten = 0
    speed_level = 0
    game_over = false
    if ui:
        ui.hide_game_over()
        ui.update_score(score)
        ui.update_speed(speed_level)
    if snake:
        snake.start(BASE_MOVE_INTERVAL)

func _on_snake_moved(new_head: Vector2i) -> void:
    if game_over:
        return
    # check wall collision
    if is_blocked(new_head):
        _trigger_game_over()
        return
    # check hazards
    for h in hazards:
        if not h:
            continue
        var hpos = h.global_position
        var hgrid = Vector2i(int(round(hpos.x / TILE_SIZE)), int(round(hpos.y / TILE_SIZE)))
        if hgrid == new_head:
            _trigger_game_over()
            return
    # check orb
    if orb_manager.consume_at(new_head):
        score += 10
        orbs_eaten += 1
        if ui:
            ui.update_score(score)
        if snake:
            snake.grow()
        # every 5 orbs increase speed and pulse background
        if orbs_eaten % 5 == 0:
            speed_level += 1
            if ui:
                ui.update_speed(speed_level)
                ui.pulse_background()
            # speed up snake
            var new_interval = max(0.05, BASE_MOVE_INTERVAL - speed_level * SPEED_STEP)
            if snake:
                snake.start(new_interval)
        # check win
        if score >= WIN_SCORE:
            print("WIN")
            _advance_arena()

func is_blocked(grid_pos: Vector2i) -> bool:
    if not current_arena:
        return false
    if current_arena.has_node("WallCells"):
        for child in current_arena.get_node("WallCells").get_children():
            if child is Position2D:
                var cpos = child.global_position
                var cgrid = Vector2i(int(round(cpos.x / TILE_SIZE)), int(round(cpos.y / TILE_SIZE)))
                if cgrid == grid_pos:
                    return true
    return false

func _trigger_game_over() -> void:
    if game_over:
        return
    game_over = true
    if snake:
        snake.stop()
    if ui:
        ui.show_game_over(score)
    print("GAME OVER %d" % score)

func _on_snake_died() -> void:
    _trigger_game_over()

func _advance_arena() -> void:
    arena_index = (arena_index + 1) % arena_scenes.size()
    # reset score and speed as we move to next arena
    score = 0
    orbs_eaten = 0
    speed_level = 0
    _load_arena(arena_index)
    _start_play()

func _process(delta: float) -> void:
    if game_over:
        if Input.is_action_just_pressed("restart"):
            _reset_game()
        elif Input.is_action_just_pressed("quit"):
            get_tree().quit()

func _reset_game() -> void:
    # reload same arena
    for h in hazards:
        if h and h.is_inside_tree():
            h.queue_free()
    hazards.clear()
    if current_arena:
        current_arena.queue_free()
        current_arena = null
    orb_manager.clear_all()
    if snake:
        snake.queue_free()
        snake = null
    score = 0
    orbs_eaten = 0
    speed_level = 0
    game_over = false
    if ui:
        ui.hide_game_over()
        ui.update_score(score)
        ui.update_speed(speed_level)
    _load_arena(arena_index)
    _start_play()
