extends Node2D
class_name GameManager

const TILE_SIZE: int = 32
const ARENA_TILES := Vector2(20, 15) # width x height in tiles
const ARENA_PIXEL_SIZE := ARENA_TILES * TILE_SIZE

var arena_index: int = 1
var arena_paths := [
	"res://game/scenes/arena_1.tscn",
	"res://game/scenes/arena_2.tscn",
	"res://game/scenes/arena_3.tscn",
]

var arena_node: Node = null
var wall_cells: Array = [] # Array of Vector2 grid cells
var hazard_nodes: Array = []
var orb_manager: Node = null
var snake_controller: Node = null
var ui_controller: Node = null
var arena_rect_pixels: Rect2 = Rect2(Vector2(160,60), ARENA_PIXEL_SIZE)

var score: int = 0
var speed_level: int = 1
var orbs_eaten: int = 0
var game_over: bool = false

func _ready() -> void:
	_setup_input()

	# instantiate UI scene if present
	var ui_path = "res://game/scenes/ui.tscn"
	if ResourceLoader.exists(ui_path):
		var ui_res = load(ui_path)
		if ui_res:
			var ui = ui_res.instantiate()
			add_child(ui)
			if ui.has_method("setup"):
				ui.setup(self)
			ui_controller = ui

	# orb manager (script-only class)
	var orb_script_path = "res://game/scripts/orb_manager.gd"
	if ResourceLoader.exists(orb_script_path):
		var orb_cls = load(orb_script_path)
		if orb_cls:
			orb_manager = orb_cls.new()
			add_child(orb_manager)
			if orb_manager.has_method("setup"):
				orb_manager.setup(self)

	# snake: prefer script class instance
	var snake_script_path = "res://game/scripts/snake_controller.gd"
	if ResourceLoader.exists(snake_script_path):
		var sc = load(snake_script_path)
		if sc:
			snake_controller = sc.new()
			add_child(snake_controller)
			if snake_controller.has_method("setup"):
				snake_controller.setup(self)
			if snake_controller.has_method("connect"):
				snake_controller.connect("ate_orb", Callable(self, "_on_snake_ate_orb"))
				snake_controller.connect("died", Callable(self, "_on_snake_died"))

	_load_arena(arena_index)

	# spawn a couple of starting orbs
	if orb_manager:
		for i in range(3):
			orb_manager.spawn_orb()

	if ui_controller:
		ui_controller.update_score(score)
		ui_controller.update_speed(speed_level)

	print("Neon Serpent")

func _setup_input() -> void:
	var actions = {
		"move_up": [KEY_W, KEY_UP],
		"move_down": [KEY_S, KEY_DOWN],
		"move_left": [KEY_A, KEY_LEFT],
		"move_right": [KEY_D, KEY_RIGHT],
		"restart": [KEY_R],
		"quit": [KEY_ESCAPE],
	}
	for name in actions.keys():
		if not InputMap.has_action(name):
			InputMap.add_action(name)
		for code in actions[name]:
			var ev = InputEventKey.new()
			ev.physical_keycode = code
			InputMap.action_add_event(name, ev)

func _load_arena(index: int) -> void:
	if arena_node and is_instance_valid(arena_node):
		arena_node.queue_free()
	for h in hazard_nodes:
		if is_instance_valid(h):
			h.queue_free()
	hazard_nodes.clear()
	wall_cells.clear()

	var path = arena_paths[(index - 1) % arena_paths.size()]
	if ResourceLoader.exists(path):
		var res = load(path)
		if res:
			arena_node = res.instantiate()
			add_child(arena_node)
			for child in arena_node.get_children():
				if typeof(child.name) == TYPE_STRING and child.name.begins_with("Wall"):
					var cell = Vector2(int(child.position.x / TILE_SIZE), int(child.position.y / TILE_SIZE))
					wall_cells.append(cell)
				elif typeof(child.name) == TYPE_STRING and child.name.begins_with("HazardSpawn"):
					# create hazard instance using script if available
					var hb_script = "res://game/scripts/hazard_ball_controller.gd"
					if ResourceLoader.exists(hb_script):
						var hb_cls = load(hb_script)
						if hb_cls:
							var hb = hb_cls.new()
							add_child(hb)
							var v = Vector2(randf() * 200 - 100, randf() * 200 - 100)
							if hb.has_method("setup"):
								hb.setup(self, v)
							h.global_position = child.global_position
							hazard_nodes.append(hb)
						else:
							var hb_path = "res://game/scenes/hazard_ball.tscn"
							if ResourceLoader.exists(hb_path):
								var hb_res = load(hb_path)
								var hb2 = hb_res.instantiate()
								add_child(hb2)
								var v2 = Vector2(randf() * 200 - 100, randf() * 200 - 100)
								if hb2.has_method("setup"):
									hb2.setup(self, v2)
								hb2.global_position = child.global_position
								hazard_nodes.append(hb2)
	arena_rect_pixels = Rect2(Vector2(160,60), ARENA_PIXEL_SIZE)

func is_cell_blocked(cell: Vector2) -> bool:
	if cell.x < 0 or cell.y < 0 or cell.x >= ARENA_TILES.x or cell.y >= ARENA_TILES.y:
		return true
	for c in wall_cells:
		if c == cell:
			return true
	return false

func get_random_free_cell() -> Vector2:
	var tries = 0
	while tries < 200:
		var x = randi() % int(ARENA_TILES.x)
		var y = randi() % int(ARENA_TILES.y)
		var cell = Vector2(x,y)
		if is_cell_blocked(cell):
			tries += 1
			continue
		if snake_controller and snake_controller.has_method("is_occupying_cell") and snake_controller.is_occupying_cell(cell):
			tries += 1
			continue
		if orb_manager and orb_manager.has_orb_at(cell):
			tries += 1
			continue
		return cell
	return Vector2(1,1)

func register_orb_eaten() -> void:
	score += 10
	orbs_eaten += 1
	if ui_controller:
		ui_controller.update_score(score)
	if orb_manager:
		# spawn one immediately; orb_manager also schedules respawn when consumed
		pass
	if orbs_eaten % 5 == 0:
		speed_level += 1
		if snake_controller and snake_controller.has_method("set_speed_level"):
			snake_controller.set_speed_level(speed_level)
		if ui_controller:
			ui_controller.update_speed(speed_level)
		_pulse_background()
	if score >= 100:
		print("WIN")
		_advance_arena()

func _pulse_background() -> void:
	var t = create_tween()
	t.tween_property(self, "modulate", Color(1.2,1.2,1.2,1), 0.15).set_trans(Tween.TRANS_SINE)
	t.tween_property(self, "modulate", Color(1,1,1,1), 0.25).set_delay(0.15)

func _advance_arena() -> void:
	arena_index = (arena_index % arena_paths.size()) + 1
	score = 0
	orbs_eaten = 0
	speed_level = 1
	if snake_controller and snake_controller.has_method("reset"):
		snake_controller.reset()
	if orb_manager and orb_manager.has_method("reset"):
		orb_manager.reset()
	_load_arena(arena_index)
	if orb_manager:
		for i in range(3):
			orb_manager.spawn_orb()

func on_snake_death(reason: String) -> void:
	if game_over:
		return
	game_over = true
	if snake_controller and snake_controller.has_method("pause_movement"):
		snake_controller.pause_movement()
	print("GAME OVER")
	print("Final score: %d" % score)
	if ui_controller and ui_controller.has_method("show_game_over"):
		ui_controller.show_game_over(score)

func _on_snake_ate_orb() -> void:
	register_orb_eaten()

func _on_snake_died(reason: String) -> void:
	on_snake_death(reason)

func _input(ev) -> void:
	if game_over:
		if Input.is_action_just_pressed("restart"):
			game_over = false
			score = 0
			orbs_eaten = 0
			speed_level = 1
			if snake_controller and snake_controller.has_method("reset"):
				snake_controller.reset()
			if orb_manager and orb_manager.has_method("reset"):
				orb_manager.reset()
			_load_arena(arena_index)
			if orb_manager:
				for i in range(3):
					orb_manager.spawn_orb()
			if ui_controller:
				ui_controller.update_score(score)
				ui_controller.update_speed(speed_level)
		elif Input.is_action_just_pressed("quit"):
			get_tree().quit()
