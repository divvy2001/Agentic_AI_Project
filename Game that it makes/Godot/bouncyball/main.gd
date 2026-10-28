extends Node2D

const PaddleScene = preload("res://paddle.tscn")
const BallScene = preload("res://ball.tscn")

var score:int = 0
var game_state:String = "running" # "running" or "gameover"
var screen_size:Vector2 = Vector2.ZERO
var paddle:Node = null
var ball:Node = null

@onready var hud_layer:CanvasLayer = CanvasLayer.new()
@onready var score_label:Label = Label.new()
@onready var gameover_label:Label = Label.new()

func _ready() -> void:
    # Window title is set in project.godot

    # Input setup
    if not InputMap.has_action("move_left"):
        InputMap.add_action("move_left")
    var ev = InputEventKey.new()
    ev.physical_keycode = KEY_LEFT
    InputMap.action_add_event("move_left", ev)

    if not InputMap.has_action("move_right"):
        InputMap.add_action("move_right")
    ev = InputEventKey.new()
    ev.physical_keycode = KEY_RIGHT
    InputMap.action_add_event("move_right", ev)

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

    # HUD
    add_child(hud_layer)
    score_label.text = "Score: 0"
    score_label.position = Vector2(8,8)
    hud_layer.add_child(score_label)

    gameover_label.text = ""
    gameover_label.visible = false
    # center the label
    gameover_label.custom_minimum_size = Vector2(400,100)
    hud_layer.add_child(gameover_label)

    # determine screen size
    var vp = get_viewport()
    if vp != null:
        screen_size = vp.get_visible_rect().size
    if screen_size == Vector2.ZERO:
        # fallback to planned resolution
        screen_size = Vector2(800,600)

    # position gameover label in center
    gameover_label.position = Vector2(screen_size.x/2 - 200, screen_size.y/2 - 50)

    # spawn entities
    spawn_entities()

func spawn_entities() -> void:
    # remove old if present
    if paddle != null:
        if paddle.get_parent() == self:
            remove_child(paddle)
        paddle.queue_free()
        paddle = null
    if ball != null:
        if ball.get_parent() == self:
            remove_child(ball)
        ball.queue_free()
        ball = null

    paddle = PaddleScene.instantiate()
    paddle.position = Vector2(screen_size.x/2, screen_size.y - 60)
    if "screen_size" in paddle:
        paddle.screen_size = screen_size
    add_child(paddle)

    ball = BallScene.instantiate()
    ball.position = paddle.position - Vector2(0, 40)
    if "screen_size" in ball:
        ball.screen_size = screen_size
    if "paddle" in ball:
        ball.paddle = paddle
    add_child(ball)
    # connect signals
    if ball.has_signal("bounced"):
        ball.connect("bounced", Callable(self, "_on_ball_bounced"))
    if ball.has_signal("missed"):
        ball.connect("missed", Callable(self, "_on_ball_missed"))
    if ball.has_method("reset"):
        ball.reset(ball.position)
    score = 0
    update_score_label()
    gameover_label.visible = false
    game_state = "running"

func _on_ball_bounced() -> void:
    score += 1
    update_score_label()

func _on_ball_missed() -> void:
    if game_state == "gameover":
        return
    game_state = "gameover"
    print("GAME OVER")
    gameover_label.text = "GAME OVER\nFinal Score: %d" % score
    gameover_label.visible = true
    if ball != null and ball.has_method("stop"):
        ball.stop()

func update_score_label() -> void:
    score_label.text = "Score: %d" % score

func _input(event) -> void:
    # restart
    if event.is_action_pressed("restart") and event.is_pressed():
        if game_state == "gameover":
            print("RESTART")
            restart_game()
    # quit
    if event.is_action_pressed("quit") and event.is_pressed():
        print("QUIT")
        get_tree().quit()

func restart_game() -> void:
    # re-create paddle and ball, reset score
    if paddle != null:
        if paddle.get_parent() == self:
            remove_child(paddle)
        paddle.queue_free()
        paddle = null
    if ball != null:
        if ball.get_parent() == self:
            remove_child(ball)
        ball.queue_free()
        ball = null
    spawn_entities()
    score = 0
    update_score_label()
    gameover_label.visible = false
    game_state = "running"
