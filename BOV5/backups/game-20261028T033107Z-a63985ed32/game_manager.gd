extends Node2D
class_name GameManager

var score: int = 0
var is_running: bool = true

@onready var seal: Node = null
@onready var ball: Node = null
@onready var score_label: Label = $CanvasLayer/ScoreLabel
@onready var game_over_label: Label = $CanvasLayer/GameOverLabel

func _ready() -> void:
	# Window title
	DisplayServer.window_set_title("Seal Bounce")
	# Ensure input actions exist
	_setup_input()
	# find nodes
	seal = $Seal
	ball = $BeachBall
	# init positions
	seal.reset_to_start()
	ball.reset_to_start()
	_update_score_label()
	game_over_label.visible = false

func _process(delta: float) -> void:
	if Input.is_action_just_pressed("restart"):
		print("RESTART")
		restart_game()
	if Input.is_action_just_pressed("quit"):
		print("QUIT")
		get_tree().quit()

func _setup_input() -> void:
	# movement
	if not InputMap.has_action("move_left"):
		InputMap.add_action("move_left")
		var ev := InputEventKey.new()
		ev.physical_keycode = KEY_LEFT
		InputMap.action_add_event("move_left", ev)
	# also add A
	var ev2 := InputEventKey.new()
	ev2.physical_keycode = KEY_A
	InputMap.action_add_event("move_left", ev2)

	if not InputMap.has_action("move_right"):
		InputMap.add_action("move_right")
		var ev3 := InputEventKey.new()
		ev3.physical_keycode = KEY_RIGHT
		InputMap.action_add_event("move_right", ev3)
	var ev4 := InputEventKey.new()
	ev4.physical_keycode = KEY_D
	InputMap.action_add_event("move_right", ev4)

	# restart
	if not InputMap.has_action("restart"):
		InputMap.add_action("restart")
		var evr := InputEventKey.new()
		evr.physical_keycode = KEY_R
		InputMap.action_add_event("restart", evr)
	# quit
	if not InputMap.has_action("quit"):
		InputMap.add_action("quit")
		var evq := InputEventKey.new()
		evq.physical_keycode = KEY_ESCAPE
		InputMap.action_add_event("quit", evq)

func increment_score() -> void:
	score += 1
	_update_score_label()

func _update_score_label() -> void:
	score_label.text = str(score)

func game_over() -> void:
	if not is_running:
		return
	is_running = false
	print("GAME OVER")
	# show label and stop ball
	game_over_label.visible = true
	if ball and ball.has_method("stop"):
		ball.stop()

func restart_game() -> void:
	is_running = true
	score = 0
	_update_score_label()
	game_over_label.visible = false
	# reset positions
	if seal and seal.has_method("reset_to_start"):
		seal.reset_to_start()
	if ball and ball.has_method("reset_to_start"):
		ball.reset_to_start()
