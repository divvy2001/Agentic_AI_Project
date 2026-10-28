extends Node2D

@onready var player_spawn: Node2D = $PlayerSpawn
@onready var rival_spawn: Node2D = $RivalSpawn
@onready var player_health_rect: ColorRect = $HUD/PlayerHealth
@onready var rival_health_rect: ColorRect = $HUD/RivalHealth
@onready var message_label: Label = $HUD/MessageLabel

var player: Node = null
var rival: Node = null
var game_over: bool = false

func _ready() -> void:
    # Input map
    if not InputMap.has_action("ui_left"):
        InputMap.add_action("ui_left")
        var e = InputEventKey.new()
        e.physical_keycode = KEY_LEFT
        InputMap.action_add_event("ui_left", e)
    if not InputMap.has_action("ui_right"):
        InputMap.add_action("ui_right")
        var e2 = InputEventKey.new()
        e2.physical_keycode = KEY_RIGHT
        InputMap.action_add_event("ui_right", e2)
    if not InputMap.has_action("ui_up"):
        InputMap.add_action("ui_up")
        var e3 = InputEventKey.new()
        e3.physical_keycode = KEY_UP
        InputMap.action_add_event("ui_up", e3)
    if not InputMap.has_action("ui_accept"):
        InputMap.add_action("ui_accept")
        var e4 = InputEventKey.new()
        e4.physical_keycode = KEY_SPACE
        InputMap.action_add_event("ui_accept", e4)
    # Restart and quit
    if not InputMap.has_action("restart"):
        InputMap.add_action("restart")
        var er = InputEventKey.new()
        er.physical_keycode = KEY_R
        InputMap.action_add_event("restart", er)
    if not InputMap.has_action("quit"):
        InputMap.add_action("quit")
        var eq = InputEventKey.new()
        eq.physical_keycode = KEY_ESCAPE
        InputMap.action_add_event("quit", eq)

    spawn_fighters()
    update_health_bars()

func spawn_fighters() -> void:
    # instantiate player and rival using script classes
    var player_script = preload("res://player.gd")
    player = player_script.new()
    player.position = player_spawn.position
    player.ui = self
    add_child(player)

    var rival_script = preload("res://rival.gd")
    rival = rival_script.new()
    rival.position = rival_spawn.position
    rival.ui = self
    rival.target = player
    add_child(rival)

func on_health_changed(side: String, new_health: int) -> void:
    if side == "player":
        var ratio = float(new_health) / float(player.max_health)
        player_health_rect.size = Vector2(300 * ratio, player_health_rect.size.y)
    elif side == "rival":
        var ratio = float(new_health) / float(rival.max_health)
        rival_health_rect.size = Vector2(300 * ratio, rival_health_rect.size.y)
    # Check for win/lose
    if not game_over:
        if new_health <= 0:
            game_over = true
            if side == "rival":
                message_label.text = "WIN"
                print("WIN")
            else:
                message_label.text = "GAME OVER"
                print("GAME OVER")
            # Freeze fighters
            player.set_physics_process(false)
            rival.set_physics_process(false)

func _process(delta: float) -> void:
    if Input.is_action_just_pressed("restart") and game_over:
        print("RESTART")
        reset_round()
    if Input.is_action_just_pressed("quit"):
        print("QUIT")
        get_tree().quit()

func reset_round() -> void:
    # remove existing fighters
    if player:
        player.queue_free()
    if rival:
        rival.queue_free()
    game_over = false
    message_label.text = ""
    spawn_fighters()
    update_health_bars()

func update_health_bars() -> void:
    if player:
        player_health_rect.size = Vector2(300, player_health_rect.size.y)
    if rival:
        rival_health_rect.size = Vector2(300, rival_health_rect.size.y)
