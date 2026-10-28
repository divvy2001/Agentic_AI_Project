extends CanvasLayer
class_name UI

var score_label: Label
var lives_label: Label
var end_label: Label

func _ready() -> void:
    score_label = Label.new()
    lives_label = Label.new()
    end_label = Label.new()
    add_child(score_label)
    add_child(lives_label)
    add_child(end_label)
    score_label.position = Vector2(10,10)
    lives_label.position = Vector2(200,10)
    end_label.position = Vector2(300, 250)
    end_label.visible = false
    end_label.add_theme_color_override("font_color", Color(1,0,0))

func update(score:int, lives:int) -> void:
    score_label.text = "Score: %d" % score
    lives_label.text = "Lives: %d" % lives

func show_end(text:String, final_score:int) -> void:
    end_label.text = "%s\nFinal Score: %d" % [text, final_score]
    end_label.visible = true

