# GameManager: manages game state, UI, win/lose, restart and quit
extends Node2D

# Game states: "playing", "win", "lose"
var state: String = "playing"
var lander: Node = null
var pad: Node = null
var speed_label: Label = null
var message_label: Label = null
var initial_lander_pos: Vector2 = Vector2.ZERO

const WIN_MAX_VERTICAL_SPEED: float = 120.0
const WIN_MAX_ANGLE_DEG: float = 20.0

func _ready() -> void:
    # Window title set in project.godot (config/name)

    # Ensure input actions exist and are bound
    _setup_input()

    # Create landing pad
    pad = LandingPad.new()
    pad.name = "LandingPad"
    add_child(pad)
    var vsize: Vector2 = get_viewport_rect().size
    pad.global_position = Vector2(vsize.x * 0.5, vsize.y - 60)

    # Create lander near top
    lander = Lander.new()
    lander.name = "Lander"
    add_child(lander)
    initial_lander_pos = Vector2(vsize.x * 0.5, 80)
    lander.reset(initial_lander_pos)
    lander.set_pad(pad)

    # Connect signal from lander
    lander.connect("touched_ground", Callable(self, "_on_lander_touched_ground"))

    # HUD
    var hud = CanvasLayer.new()
    hud.name = "HUD"
    add_child(hud)

    speed_label = Label.new()
    speed_label.name = "SpeedLabel"
    speed_label.position = Vector2(10, 10)
    speed_label.text = "Speed: 0"
    hud.add_child(speed_label)

    message_label = Label.new()
    message_label.name = "MessageLabel"
    # Centering: position the label so it appears centered on screen
    message_label.position = Vector2(vsize.x * 0.5 - 100, vsize.y * 0.5 - 20)
    message_label.size = Vector2(200, 40)
    message_label.text = ""
    message_label.visible = true
    hud.add_child(message_label)

    state = "playing"

func _setup_input() -> void:
    # Add actions and bind keys (safe even if they exist)
    if not InputMap.has_action("ui_up"):
        InputMap.add_action("ui_up")
    var ev = InputEventKey.new()
    ev.physical_keycode = KEY_UP
    InputMap.action_add_event("ui_up", ev)

    if not InputMap.has_action("ui_left"):
        InputMap.add_action("ui_left")
    ev = InputEventKey.new()
    ev.physical_keycode = KEY_LEFT
    InputMap.action_add_event("ui_left", ev)

    if not InputMap.has_action("ui_right"):
        InputMap.add_action("ui_right")
    ev = InputEventKey.new()
    ev.physical_keycode = KEY_RIGHT
    InputMap.action_add_event("ui_right", ev)

    if not InputMap.has_action("restart"):
        InputMap.add_action("restart")
    ev = InputEventKey.new()
    ev.physical_keycode = KEY_R
    InputMap.action_add_event("restart", ev)

    if not InputMap.has_action("quit"):
        InputMap.add_action("quit")
    ev = InputEventKey.new()
    ev.physical_keycode = KEY_ESCAPE
    InputMap.action_add_event("quit", ev)

func _process(delta: float) -> void:
    if lander != null:
        # Update speed display
        var spd = int(lander.velocity.length())
        speed_label.text = "Speed: %d" % spd

    # Restart
    if Input.is_action_just_pressed("restart"):
        print("RESTART")
        _do_restart()

    # Quit
    if Input.is_action_just_pressed("quit"):
        print("QUIT")
        get_tree().quit()

func _on_lander_touched_ground(pos: Vector2, vertical_speed: float, angle_deg: float) -> void:
    if state != "playing":
        return

    var landed_on_pad: bool = false
    if pad != null:
        landed_on_pad = pad.contains_x(pos.x)

    var win: bool = landed_on_pad and vertical_speed <= WIN_MAX_VERTICAL_SPEED and angle_deg <= WIN_MAX_ANGLE_DEG
    if win:
        state = "win"
        message_label.text = "WIN"
        message_label.modulate = Color(0.2, 0.9, 0.2)
        print("WIN")
        if lander:
            lander.freeze()
    else:
        state = "lose"
        message_label.text = "GAME OVER"
        message_label.modulate = Color(0.9, 0.2, 0.2)
        print("GAME OVER")
        if lander:
            lander.freeze()

func _do_restart() -> void:
    # Reset game objects to initial state
    state = "playing"
    message_label.text = ""
    if lander:
        lander.reset(initial_lander_pos)
        lander.set_pad(pad)

func _notification(what):
    if what == NOTIFICATION_EXIT_TREE:
        # nothing special
        pass
