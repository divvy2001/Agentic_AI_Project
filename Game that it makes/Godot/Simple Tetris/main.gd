extends Node2D
class_name Main

# Simple Tetris implementation per Plan (Godot 4 API).
@onready var score_label: Label = $CanvasLayer/ScoreLabel
@onready var game_over_label: Label = $CanvasLayer/GameOverLabel

const COLS: int = 10
const ROWS: int = 20
const VIEW_W: int = 400
const VIEW_H: int = 600
const TILE_SIZE: int = int(min(float(VIEW_W) / COLS, float(VIEW_H) / ROWS)) # 30
const GRID_WIDTH: int = COLS * TILE_SIZE
const GRID_LEFT: int = int((VIEW_W - GRID_WIDTH) / 2)

# Drop timing
var drop_interval: float = 0.5
var drop_timer: float = 0.0

# Grid: rows of columns. Each cell is Color or null.
var grid: Array = []

var current_piece: Dictionary = {}
var score: int = 0
var game_over: bool = false

# Define shapes: each value is an Array of rotations, each rotation is an Array of Vector2i offsets
const SHAPES: Dictionary = {
	"O": [
		[Vector2i(0,0), Vector2i(1,0), Vector2i(0,1), Vector2i(1,1)]
	],
	"I": [
		[Vector2i(-1,0), Vector2i(0,0), Vector2i(1,0), Vector2i(2,0)],
		[Vector2i(0,-1), Vector2i(0,0), Vector2i(0,1), Vector2i(0,2)]
	],
	"L": [
		[Vector2i(-1,0), Vector2i(0,0), Vector2i(1,0), Vector2i(1,1)],
		[Vector2i(0,-1), Vector2i(0,0), Vector2i(0,1), Vector2i(1,-1)],
		[Vector2i(-1,-1), Vector2i(-1,0), Vector2i(0,0), Vector2i(1,0)],
		[Vector2i(-1,1), Vector2i(0,-1), Vector2i(0,0), Vector2i(0,1)]
	],
	"T": [
		[Vector2i(-1,0), Vector2i(0,0), Vector2i(1,0), Vector2i(0,1)],
		[Vector2i(0,-1), Vector2i(0,0), Vector2i(0,1), Vector2i(1,0)],
		[Vector2i(-1,0), Vector2i(0,0), Vector2i(1,0), Vector2i(0,-1)],
		[Vector2i(0,-1), Vector2i(0,0), Vector2i(0,1), Vector2i(-1,0)]
	]
}

const COLORS: Dictionary = {
	"O": Color8(240,200,40),
	"I": Color8(40,200,240),
	"L": Color8(240,140,40),
	"T": Color8(160,80,240)
}

func _ready() -> void:
	randomize()
	# Ensure input actions exist
	_add_input("move_left", KEY_LEFT)
	_add_input("move_right", KEY_RIGHT)
	_add_input("soft_drop", KEY_DOWN)
	_add_input("rotate", KEY_UP)
	_add_input("restart", KEY_R)
	_add_input("quit", KEY_ESCAPE)

	# Initialize grid and game
	reset_game()

	# Set initial labels
	score_label.text = "Score: %d" % score
	game_over_label.visible = false
	set_process(true)
	queue_redraw()

func _add_input(name: String, key: int) -> void:
	if not InputMap.has_action(name):
		InputMap.add_action(name)
	var ev := InputEventKey.new()
	ev.keycode = key
	InputMap.action_add_event(name, ev)

func reset_game() -> void:
	grid = []
	for r in range(ROWS):
		var row := []
		for c in range(COLS):
			row.append(null)
		grid.append(row)
	score = 0
	game_over = false
	print("RESTART")
	spawn_piece()
	queue_redraw()

func spawn_piece() -> void:
	var keys: Array = SHAPES.keys()
	var choice: String = keys[randi() % keys.size()] as String
	var rotations: Array = SHAPES[choice] as Array
	var rot_idx: int = 0
	# spawn at top-middle
	var px := int(COLS / 2)
	var py := 0
	current_piece = {
		"shape": choice,
		"rot": rot_idx,
		"x": px,
		"y": py,
		"color": COLORS[choice]
	}
	# If initial placement collides -> game over
	if not can_move(0,0,0):
		game_over = true
		print("GAME OVER")
		game_over_label.visible = true
	else:
		game_over_label.visible = false
	queue_redraw()

func can_move(dx: int, dy: int, rotation_delta: int = 0) -> bool:
	if game_over:
		return false
	var shape: String = current_piece.get("shape") as String
	var rot: int = (current_piece.get("rot") as int + rotation_delta) % SHAPES[shape].size()
	var blocks: Array = SHAPES[shape][rot] as Array
	for off in blocks:
		var nx := current_piece.get("x") as int + int(off.x) + dx
		var ny := current_piece.get("y") as int + int(off.y) + dy
		if nx < 0 or nx >= COLS:
			return false
		if ny < 0:
			continue
		if ny >= ROWS:
			return false
		if grid[ny][nx] != null:
			return false
	return true

func lock_piece() -> void:
	var shape: String = current_piece.get("shape") as String
	var rot: int = current_piece.get("rot") as int
	var blocks: Array = SHAPES[shape][rot] as Array
	for off in blocks:
		var nx := (current_piece.get("x") as int) + int(off.x)
		var ny := (current_piece.get("y") as int) + int(off.y)
		if ny >= 0 and ny < ROWS and nx >=0 and nx < COLS:
			grid[ny][nx] = current_piece.get("color")
	# After locking, clear lines
	var cleared := clear_lines()
	if cleared > 0:
		score += 100 * cleared
	# Spawn next
	spawn_piece()
	queue_redraw()

func clear_lines() -> int:
	var cleared := 0
	for row_idx in range(ROWS - 1, -1, -1):
		var full := true
		for c in range(COLS):
			if grid[row_idx][c] == null:
				full = false
				break
		if full:
			# remove this row and insert empty at top
			grid.remove_at(row_idx)
			var empty_row := []
			for c in range(COLS):
				empty_row.append(null)
			grid.insert(0, empty_row)
			cleared += 1
	# Score addition handled by caller
	return cleared

func _process(delta: float) -> void:
	if game_over:
		return
	drop_timer += delta
	if drop_timer >= drop_interval:
		drop_timer = 0.0
		if can_move(0,1,0):
			current_piece["y"] += 1
		else:
			# lock
			lock_piece()
	# Update HUD
	score_label.text = "Score: %d" % score
	queue_redraw()

func _draw() -> void:
	# background
	draw_rect(Rect2(Vector2.ZERO, Vector2(VIEW_W, VIEW_H)), Color(0.1,0.1,0.1))
	# draw grid background
	draw_rect(Rect2(Vector2(GRID_LEFT,0), Vector2(GRID_WIDTH, ROWS * TILE_SIZE)), Color(0,0,0))
	# draw locked blocks
	for r in range(ROWS):
		for c in range(COLS):
			var cell = grid[r][c]
			if cell != null:
				var col: Color = cell as Color
				var pos := Vector2(GRID_LEFT + c * TILE_SIZE, r * TILE_SIZE)
				draw_rect(Rect2(pos, Vector2(TILE_SIZE,TILE_SIZE)), col)
	# draw current piece
	if current_piece.size() > 0 and not game_over:
		var shape: String = current_piece.get("shape") as String
		var rot: int = current_piece.get("rot") as int
		var blocks: Array = SHAPES[shape][rot] as Array
		var col: Color = current_piece.get("color") as Color
		for off in blocks:
			var nx := (current_piece.get("x") as int) + int(off.x)
			var ny := (current_piece.get("y") as int) + int(off.y)
			if ny >= 0:
				var pos := Vector2(GRID_LEFT + nx * TILE_SIZE, ny * TILE_SIZE)
				draw_rect(Rect2(pos, Vector2(TILE_SIZE, TILE_SIZE)), col)

func _unhandled_input(ev: InputEvent) -> void:
	if ev is InputEventKey and ev.pressed and not ev.echo:
		if Input.is_action_pressed("move_left") and not Input.is_action_pressed("move_right"):
			if can_move(-1,0,0):
				current_piece["x"] -= 1
				print("MOVE LEFT")
				queue_redraw()
			return
		if Input.is_action_pressed("move_right") and not Input.is_action_pressed("move_left"):
			if can_move(1,0,0):
				current_piece["x"] += 1
				print("MOVE RIGHT")
				queue_redraw()
			return
		if Input.is_action_pressed("soft_drop"):
			# soft drop moves down one row immediately if possible
			if can_move(0,1,0):
				current_piece["y"] += 1
				print("SOFT DROP")
			else:
				# cannot move down, lock immediately
				lock_piece()
			queue_redraw()
			return
		if Input.is_action_pressed("rotate"):
			# attempt rotation
			if can_move(0,0,1):
				current_piece["rot"] = (current_piece["rot"] + 1) % SHAPES[current_piece["shape"]].size()
				print("ROTATE")
				queue_redraw()
			return
		if Input.is_action_pressed("restart"):
			reset_game()
			return
		if Input.is_action_pressed("quit"):
			print("QUIT")
			get_tree().quit()
