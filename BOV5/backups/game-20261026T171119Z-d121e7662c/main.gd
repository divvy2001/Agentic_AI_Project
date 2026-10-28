extends Node2D

# Main game controller for Bounce Catch

const WIN_SCORE: int = 15

var score: int = 0
var lives: int = 3
var state: String = "playing" # "playing", "win", "game_over"
var balls: Array = []

var PaddleScene = preload("res://paddle.tscn")
var BallScene = preload("res://ball.tscn")

onready var spawn_timer: Timer = Timer.new()
onready var hud_layer: CanvasLayer = CanvasLayer.new()
onready var score_label: Label = Label.new()
onready var lives_label: Label = Label.new()
onready var message_label: Label = Label.new()

func _ready() -> void:
    # Window title
    if Engine.has_singleton("OS"):
        OS.set_window_title("Bounce Catch")

    randomize()

    # Ensure input actions
    if not InputMap.has_action("move_left"):
        InputMap.add_action("move_left")
    var ev = InputEventKey.new()
    ev.physical_keycode = KEY_LEFT
    InputMap.action_add_event("move_left", ev)
    var ev2 = InputEventKey.new()
    ev2.physical_keycode = KEY_A
    InputMap.action_add_event("move_left", ev2)

    if not InputMap.has_action("move_right"):
        InputMap.add_action("move_right")
    var ev3 = InputEventKey.new()
    ev3.physical_keycode = KEY_RIGHT
    InputMap.action_add_event("move_right", ev3)
    var ev4 = InputEventKey.new()
    ev4.physical_keycode = KEY_D
    InputMap.action_add_event("move_right", ev4)

    if not InputMap.has_action("restart"):
        InputMap.add_action("restart")
    var evr = InputEventKey.new()
    evr.physical_keycode = KEY_R
    InputMap.action_add_event("restart", evr)

    if not InputMap.has_action("quit"):
        InputMap.add_action("quit")
    var evq = InputEventKey.new()
    evq.physical_keycode = KEY_ESCAPE
    InputMap.action_add_event("quit", evq)

    # Create paddle and place near bottom center
    var paddle = PaddleScene.instantiate()
    paddle.name = "Paddle"
    add_child(paddle)
    var view_size = get_viewport_rect().size
    paddle.position = Vector2(view_size.x/2, view_size.y - 48)

    # Setup HUD
    hud_layer.name = "HUD"
    add_child(hud_layer)

    score_label.name = "ScoreLabel"
    score_label.text = "Score: %d" % score
    score_label.position = Vector2(10, 10)
    hud_layer.add_child(score_label)

    lives_label.name = "LivesLabel"
    lives_label.text = "Lives: %d" % lives
    lives_label.position = Vector2(10, 34)
    hud_layer.add_child(lives_label)

    message_label.name = "MessageLabel"
    message_label.text = ""
    message_label.position = Vector2(view_size.x/2 - 60, view_size.y/2 - 20)
    message_label.visible = false
    hud_layer.add_child(message_label)

    # Spawn timer
    spawn_timer.one_shot = false
    spawn_timer.wait_time = 1.0
    spawn_timer.autostart = true
    spawn_timer.name = "SpawnTimer"
    add_child(spawn_timer)
    spawn_timer.start()
    spawn_timer.timeout.connect(Callable(self, "_on_spawn_timer_timeout"))

    # Start game state
    score = 0
    lives = 3
    state = "playing"
    update_hud()

func _on_spawn_timer_timeout() -> void:
    if state != "playing":
        return
    spawn_ball()

func spawn_ball() -> void:
    var view_size = get_viewport_rect().size
    var b = BallScene.instantiate()
    b.position = Vector2(randf_range(16, view_size.x - 16), 16)
    # Give a small random horizontal velocity
    b.velocity = Vector2(randf_range(-50, 50), 40)
    add_child(b)
    balls.append(b)
    b.add_to_group("balls")
    # Connect signals
    if not b.is_connected("bounced", Callable(self, "_on_ball_bounced")):
        b.connect("bounced", Callable(self, "_on_ball_bounced"), [b])
    if not b.is_connected("missed", Callable(self, "_on_ball_missed")):
        b.connect("missed", Callable(self, "_on_ball_missed"), [b])

func _on_ball_bounced(ball: Node) -> void:
    if state != "playing":
        return
    score += 1
    update_hud()
    # Ensure the ball is tracked
    if balls.has(ball) == false:
        balls.append(ball)
    if score >= WIN_SCORE:
        handle_win()

func _on_ball_missed(ball: Node) -> void:
    if state != "playing":
        return
    # Remove from tracking if present
    if balls.has(ball):
        balls.erase(ball)
    lives -= 1
    update_hud()
    if lives <= 0:
        handle_game_over()

func handle_win() -> void:
    if state == "win":
        return
    state = "win"
    spawn_timer.stop()
    message_label.text = "WIN"
    message_label.visible = true
    print("WIN")
    print("SCORE:", score)

func handle_game_over() -> void:
    if state == "game_over":
        return
    state = "game_over"
    spawn_timer.stop()
    message_label.text = "GAME OVER"
    message_label.visible = true
    print("GAME OVER")
    print("SCORE:", score)

func update_hud() -> void:
    score_label.text = "Score: %d" % score
    lives_label.text = "Lives: %d" % lives

func _process(delta: float) -> void:
    # Restart or quit handling
    if Input.is_action_just_pressed("restart"):
        restart_game()
    if Input.is_action_just_pressed("quit"):
        get_tree().quit()

func restart_game() -> void:
    # Only perform full reset if not playing, or always allow restart
    # Clear existing balls
    for b in balls.duplicate():
        if is_instance_valid(b):
            b.queue_free()
    balls.clear()
    # Reset state
    score = 0
    lives = 3
    state = "playing"
    message_label.visible = false
    update_hud()
    spawn_timer.start()
