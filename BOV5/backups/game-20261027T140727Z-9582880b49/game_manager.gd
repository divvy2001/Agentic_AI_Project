extends Node2D

# GameManager handles input setup, HUD updates, win/lose, restart and quit

@onready var player: Node = $Player
@onready var rival: Node = $Rival
var hud_player_bar_fg: ColorRect
var hud_rival_bar_fg: ColorRect
@onready var win_label: Label = $HUD/WinLabel

var player_start_pos: Vector2
var rival_start_pos: Vector2

var hud_player_bar_full_width: float = 300.0
var hud_rival_bar_full_width: float = 300.0

func _ready() -> void:
    # set window title via project settings (project.godot) should apply, but ensure in case
    if ProjectSettings.has_setting("application/config/name"):
        var name = ProjectSettings.get_setting("application/config/name")
        if name:
            DisplayServer.window_set_title(str(name))

    _ensure_input_actions()

    # cache start positions
    player_start_pos = player.global_position
    rival_start_pos = rival.global_position

    # find HUD elements safely (use get_node_or_null to avoid tscn ordering issues)
    var hud := get_node_or_null("HUD")
    if hud:
        hud_player_bar_fg = hud.get_node_or_null("PlayerBar/Foreground") if hud.has_node("PlayerBar/Foreground") else null
        hud_rival_bar_fg = hud.get_node_or_null("RivalBar/Foreground") if hud.has_node("RivalBar/Foreground") else null
        # If missing, create simple ColorRect placeholders so updates won't error
        if not hud_player_bar_fg:
            var pb := hud.get_node_or_null("PlayerBar")
            if not pb:
                pb = ColorRect.new()
                pb.name = "PlayerBar"
                pb.rect_position = Vector2(50,10)
                hud.add_child(pb)
            hud_player_bar_fg = ColorRect.new()
            hud_player_bar_fg.name = "Foreground"
            hud_player_bar_fg.color = Color(1,0,0)
            pb.add_child(hud_player_bar_fg)
        if not hud_rival_bar_fg:
            var rb := hud.get_node_or_null("RivalBar")
            if not rb:
                rb = ColorRect.new()
                rb.name = "RivalBar"
                rb.rect_position = Vector2(450,10)
                hud.add_child(rb)
            hud_rival_bar_fg = ColorRect.new()
            hud_rival_bar_fg.name = "Foreground"
            hud_rival_bar_fg.color = Color(0,0,1)
            rb.add_child(hud_rival_bar_fg)

    # connect signals
    if player.has_signal("health_changed"):
        player.health_changed.connect(Callable(self, "_on_player_health_changed"))
    if player.has_signal("died"):
        player.died.connect(Callable(self, "_on_player_died"))
    if rival.has_signal("health_changed"):
        rival.health_changed.connect(Callable(self, "_on_rival_health_changed"))
    if rival.has_signal("died"):
        rival.died.connect(Callable(self, "_on_rival_died"))

    # initialize HUD
    _on_player_health_changed(player.max_health)
    _on_rival_health_changed(rival.max_health)
    if win_label:
        win_label.visible = false

func _ensure_input_actions() -> void:
    # Define actions and bind keys (arrows, space, R, Escape)
    var a_left = "ui_left"
    var a_right = "ui_right"
    var a_up = "ui_up"
    var a_attack = "ui_attack"
    var a_restart = "restart"
    var a_quit = "quit"

    _add_key_action(a_left, KEY_LEFT)
    _add_key_action(a_left, KEY_A)
    _add_key_action(a_right, KEY_RIGHT)
    _add_key_action(a_right, KEY_D)
    _add_key_action(a_up, KEY_UP)
    _add_key_action(a_up, KEY_W)
    _add_key_action(a_attack, KEY_SPACE)
    _add_key_action(a_restart, KEY_R)
    _add_key_action(a_quit, KEY_ESCAPE)

func _add_key_action(name: String, keycode: int) -> void:
    if not InputMap.has_action(name):
        InputMap.add_action(name)
    var ev := InputEventKey.new()
    ev.physical_keycode = keycode
    InputMap.action_add_event(name, ev)

func _process(delta: float) -> void:
    # handle restart and quit input here for prints/behavior
    if Input.is_action_just_pressed("restart"):
        print("RESTART")
        restart_game()
    if Input.is_action_just_pressed("quit"):
        print("QUIT")
        get_tree().quit()

func _on_player_health_changed(new_health: int) -> void:
    var pct = float(new_health) / float(player.max_health)
    var clamped: float = clamp(pct, 0.0, 1.0)
    if hud_player_bar_fg:
        # Set rect_size.x so the designer can edit the foreground size in the editor
        var full := hud_player_bar_full_width
        if full <= 0:
            full = hud_player_bar_fg.rect_size.x
        hud_player_bar_fg.rect_size = Vector2(clamped * full, hud_player_bar_fg.rect_size.y)

func _on_rival_health_changed(new_health: int) -> void:
    var pct = float(new_health) / float(rival.max_health)
    var clamped: float = clamp(pct, 0.0, 1.0)
    if hud_rival_bar_fg:
        var full := hud_rival_bar_full_width
        if full <= 0:
            full = hud_rival_bar_fg.rect_size.x
        hud_rival_bar_fg.rect_size = Vector2(clamped * full, hud_rival_bar_fg.rect_size.y)

func _on_player_died() -> void:
    # player died -> GAME OVER
    win_label.text = "GAME OVER"
    win_label.visible = true
    print("GAME OVER")
    get_tree().paused = true

func _on_rival_died() -> void:
    win_label.text = "WIN"
    win_label.visible = true
    print("WIN")
    get_tree().paused = true

func restart_game() -> void:
    # hide win text
    win_label.visible = false
    # reset fighters
    if player.has_method("reset"):
        player.reset(player_start_pos)
    if rival.has_method("reset"):
        rival.reset(rival_start_pos)
    # unpause
    get_tree().paused = false
    # refresh HUD
    _on_player_health_changed(player.max_health)
    _on_rival_health_changed(rival.max_health)
