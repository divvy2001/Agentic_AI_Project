extends Node2D

var score: int = 0
var phase: String = "PLAYING"

func award_point() -> void:
    score += 1
    # BUG: WIN should happen at exactly score=3.
    if score > 3:
        phase = "WIN"
