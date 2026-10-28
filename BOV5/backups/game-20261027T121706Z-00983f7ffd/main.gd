extends Node2D

# Main game controller

# We'll load scripts at runtime to avoid parse-time class resolution issues

var maze = null
var mouse: Node = null
var cats := []
var ui: Node = null

var score := 0
var lives := 3
var game_state := "playing" # playing, won, over

# start tiles
var mouse_start := Vector2(1,1)
var cat_starts := [Vector2(13,13), Vector2(13,1)]

func _ready() -> void:
    DisplayServer.window_set_title("Crumb Chase")
    _setup_input()
    _start_game()

func _setup_input() -> void:
    # add InputMap actions
    var a := InputMap.has_action("turn_up")
    InputMap.add_action("turn_up")
    var e = InputEventKey.new()
    e.physical_keycode = KEY_UP
    InputMap.action_add_event("turn_up", e)
    var e2 = InputEventKey.new()
    e2.physical_keycode = KEY_W
    InputMap.action_add_event("turn_up", e2)

    InputMap.add_action("turn_down")
    var d = InputEventKey.new(); d.physical_keycode = KEY_DOWN; InputMap.action_add_event("turn_down", d)
    var d2 = InputEventKey.new(); d2.physical_keycode = KEY_S; InputMap.action_add_event("turn_down", d2)

    InputMap.add_action("turn_left")
    var l = InputEventKey.new(); l.physical_keycode = KEY_LEFT; InputMap.action_add_event("turn_left", l)
    var l2 = InputEventKey.new(); l2.physical_keycode = KEY_A; InputMap.action_add_event("turn_left", l2)

    InputMap.add_action("turn_right")
    var r = InputEventKey.new(); r.physical_keycode = KEY_RIGHT; InputMap.action_add_event("turn_right", r)
    var r2 = InputEventKey.new(); r2.physical_keycode = KEY_D; InputMap.action_add_event("turn_right", r2)

    InputMap.add_action("restart")
    var re = InputEventKey.new(); re.physical_keycode = KEY_R; InputMap.action_add_event("restart", re)

    InputMap.add_action("quit")
    var q = InputEventKey.new(); q.physical_keycode = KEY_ESCAPE; InputMap.action_add_event("quit", q)

func _start_game() -> void:
    # create maze by instancing the Maze script
    var maze_inst = load("res://maze.gd").new()
    add_child(maze_inst)
    maze = maze_inst

    # create mouse
    var mouse_inst = load("res://mouse.gd").new()
    add_child(mouse_inst)
    mouse = mouse_inst
    mouse.setup(maze, mouse_start)
    mouse.connect("ate_crumb", Callable(self, "_on_mouse_ate_crumb"))
    mouse.connect("caught", Callable(self, "_on_mouse_caught"))

    # create cats
    cats = []
    for i in range(2):
        var cinst = load("res://cat.gd").new()
        add_child(cinst)
        var c = cinst
        c.setup(maze, cat_starts[i], mouse)
        cats.append(c)

    # ui
    var ui_inst = load("res://ui.gd").new()
    add_child(ui_inst)
    ui = ui_inst
    ui.update(score, lives)
    game_state = "playing"

func _process(delta: float) -> void:
    if game_state != "playing":
        return
    # handle input
    if Input.is_action_just_pressed("turn_up"):
        print("TURN UP")
        mouse.set_intended_direction(Vector2(0, -1))
    if Input.is_action_just_pressed("turn_down"):
        print("TURN DOWN")
        mouse.set_intended_direction(Vector2(0, 1))
    if Input.is_action_just_pressed("turn_left"):
        print("TURN LEFT")
        mouse.set_intended_direction(Vector2(-1, 0))
    if Input.is_action_just_pressed("turn_right"):
        print("TURN RIGHT")
        mouse.set_intended_direction(Vector2(1, 0))
    if Input.is_action_just_pressed("restart"):
        print("RESTART")
        restart_game()
    if Input.is_action_just_pressed("quit"):
        print("QUIT")
        get_tree().quit()

func _on_mouse_ate_crumb(tile: Vector2) -> void:
    score += 10
    ui.update(score, lives)
    # check win
    if maze.get_crumb_count() == 0:
        _on_win()

func _on_mouse_caught() -> void:
    lives -= 1
    ui.update(score, lives)
    # respawn animation placeholder: make mouse spin by rotating and fading via modulate
    mouse.set_active(false)
    for c in cats:
        c.set_active(false)
    # simple immediate respawn
    if lives <= 0:
        _on_game_over()
    else:
        # reset positions
        mouse.respawn(mouse_start)
        for i in range(cats.size()):
            cats[i].respawn(cat_starts[i])
        mouse.set_active(true)
        for c in cats:
            c.set_active(true)

func _on_win() -> void:
    game_state = "won"
    ui.show_end("WIN", score)
    print("WIN")

func _on_game_over() -> void:
    game_state = "over"
    ui.show_end("GAME OVER", score)
    print("GAME OVER")

func restart_game() -> void:
    # restore initial state
    score = 0
    lives = 3
    maze.reset()
    mouse.respawn(mouse_start)
    for i in range(cats.size()):
        cats[i].respawn(cat_starts[i])
    ui.update(score, lives)
    ui.end_label.visible = false
    game_state = "playing"

func set_layout(layout:Array) -> void:
    maze.build_from_layout(layout)
    # reposition characters if necessary
    mouse.respawn(mouse_start)
    for i in range(cats.size()):
        cats[i].respawn(cat_starts[i])
