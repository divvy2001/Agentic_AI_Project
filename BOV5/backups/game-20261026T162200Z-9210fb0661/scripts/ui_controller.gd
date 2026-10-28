extends CanvasLayer
class_name UIController

var gm: Node = null
onready var score_label = null
onready var speed_label = null
onready var gameover_label = null
onready var prompt_label = null

func _ready() -> void:
    score_label = get_node_or_null("ScoreLabel")
    speed_label = get_node_or_null("SpeedLabel")
    gameover_label = get_node_or_null("GameOverLabel")
    prompt_label = get_node_or_null("PromptLabel")
    if gameover_label:
        gameover_label.visible = false
    if prompt_label:
        prompt_label.visible = false

func setup(manager: Node) -> void:
    gm = manager
    update_score(0)
    update_speed(1)

func update_score(s: int) -> void:
    if score_label:
        score_label.text = "Score: %d" % s

func update_speed(level: int) -> void:
    if speed_label:
        speed_label.text = "Speed: %d" % level

func show_game_over(final_score: int) -> void:
    if gameover_label:
        gameover_label.text = "GAME OVER\nFinal: %d" % final_score
        gameover_label.visible = true
    if prompt_label:
        prompt_label.text = "Press R to restart, Esc to quit"
        prompt_label.visible = true
