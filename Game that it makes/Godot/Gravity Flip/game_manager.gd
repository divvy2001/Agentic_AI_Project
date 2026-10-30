extends Node2D

class_name GameManager

@export var playing: bool = true
var score: int = 0
var platforms: Array = []
var player = null

@onready var score_label: Label = $HUD/ScoreLabel
@onready var game_over_label: Label = $HUD/GameOver

func _ready() -> void:
	# Ensure input actions exist
	if not InputMap.has_action("flip"):
		InputMap.add_action("flip")
		var ie := InputEventKey.new()
		ie.physical_keycode = KEY_SPACE
		InputMap.action_add_event("flip", ie)
	if not InputMap.has_action("restart"):
		InputMap.add_action("restart")
		var ir := InputEventKey.new()
		ir.physical_keycode = KEY_R
		InputMap.action_add_event("restart", ir)
	if not InputMap.has_action("quit"):
		InputMap.add_action("quit")
		var iq := InputEventKey.new()
		iq.physical_keycode = KEY_ESCAPE
		InputMap.action_add_event("quit", iq)

	# gather platforms and player (children of this node)
	platforms.clear()
	for child in get_children():
		if child is Platform:
			platforms.append(child)
			# allow platform to draw/collision to initialize
			child.queue_redraw()
		elif child.name == "Player":
			player = child

	# connect player signals
	if player != null:
		player.connect("fell", Callable(self, "_on_player_fell"))
		player.connect("passed_platform", Callable(self, "_on_player_passed"))

	update_score_label()
	game_over_label.text = ""
	playing = true

func _process(delta: float) -> void:
	if Input.is_action_just_pressed("flip") and playing and player != null:
		player.flip_gravity()
		print("FLIP GRAVITY")

	if Input.is_action_just_pressed("restart"):
		reset_game()
		print("RESTART")

	if Input.is_action_just_pressed("quit"):
		print("QUIT")
		get_tree().quit()

func _on_player_passed(platform) -> void:
	if platform and not platform.scored:
		platform.scored = true
		score += 1
		update_score_label()

func _on_player_fell() -> void:
	# End the run
	if not playing:
		return
	playing = false
	# stop player from processing
	if player:
		player.set_physics_process(false)
	# show game over and final score
	game_over_label.text = "GAME OVER\nSCORE: %d" % score
	print("GAME OVER")

func reset_game() -> void:
	score = 0
	for p in platforms:
		p.reset()
	update_score_label()
	if player:
		player.reset()
		player.set_physics_process(true)
	game_over_label.text = ""
	playing = true

func update_score_label() -> void:
	score_label.text = "SCORE: %d" % score

# Utility registration method if a platform chooses to call it
func register_platform(platform: Node) -> void:
	if platform not in platforms:
		platforms.append(platform)
