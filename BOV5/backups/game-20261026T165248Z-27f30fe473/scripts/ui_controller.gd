extends CanvasLayer
class_name UIController

var score_label: Label
var speed_label: Label
var game_over_label: Label
var prompt_label: Label
var bg_rect: ColorRect

func _ready() -> void:
    score_label = $MarginContainer/VBoxContainer/ScoreLabel
    speed_label = $MarginContainer/VBoxContainer/SpeedLabel
    game_over_label = $GameOver
    prompt_label = $Prompt
    bg_rect = $BG
    hide_game_over()

func update_score(p_score: int) -> void:
    if score_label:
        score_label.text = "Score: %d" % p_score

func update_speed(p_speed: int) -> void:
    if speed_label:
        speed_label.text = "Speed: %d" % p_speed

func show_game_over(final_score: int) -> void:
    if game_over_label:
        game_over_label.visible = true
        game_over_label.text = "GAME OVER"
    if prompt_label:
        prompt_label.visible = true
        prompt_label.text = "Press R to restart, Esc to quit"

func hide_game_over() -> void:
    if game_over_label:
        game_over_label.visible = false
    if prompt_label:
        prompt_label.visible = false

func pulse_background() -> void:
    if bg_rect:
        bg_rect.modulate = Color(0.5,0.5,1.0,1)
        bg_rect.create_timer(0.15).connect("timeout", Callable(self, "_reset_bg"))

func _reset_bg() -> void:
    if bg_rect:
        bg_rect.modulate = Color(1,1,1,1)
