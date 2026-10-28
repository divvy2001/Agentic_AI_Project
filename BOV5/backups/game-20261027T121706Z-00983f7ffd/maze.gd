extends Node2D
class_name Maze

const WIDTH := 15
const HEIGHT := 15
const TILE_SIZE := 32

var walls := []
var crumbs := {} # Dictionary keyed by Vector2 -> Crumb
var crumb_count := 0
var offset := Vector2.ZERO

@onready var CrumbScene = preload("res://crumb.gd")

func _ready() -> void:
    # center the grid in 800x600 (as planned)
    var grid_px = Vector2(WIDTH * TILE_SIZE, HEIGHT * TILE_SIZE)
    offset = Vector2((800 - grid_px.x) / 2, (600 - grid_px.y) / 2)
    build_default()
    call_deferred("update")

func build_default() -> void:
    # create walls array and place walls around border and a simple pattern
    walls = []
    for y in range(HEIGHT):
        var row := []
        for x in range(WIDTH):
            var is_wall := false
            # border walls
            if x == 0 or y == 0 or x == WIDTH - 1 or y == HEIGHT - 1:
                is_wall = true
            # simple inner pattern: walls on even coords except near start (1,1)
            elif x % 2 == 0 and y % 2 == 0:
                is_wall = true
            row.append(is_wall)
        walls.append(row)
    # Carve some passages to ensure start area open
    walls[1][1] = false
    walls[2][1] = false
    walls[1][2] = false
    # Remove a few more to make playable
    walls[3][1] = false
    walls[3][2] = false
    walls[5][1] = false
    # create crumbs on every open tile
    _create_crumbs()

func build_from_layout(layout:Array) -> void:
    # layout expected as Array of Array of int (1 wall, 0 open)
    if layout.size() != HEIGHT:
        build_default()
        return
    walls = []
    for y in range(HEIGHT):
        var row := []
        var layrow = layout[y]
        for x in range(WIDTH):
            var is_wall = false
            if int(layrow[x]) == 1:
                is_wall = true
            row.append(is_wall)
        walls.append(row)
    _create_crumbs()
    call_deferred("update")

func _create_crumbs() -> void:
    # clear existing crumbs
    for k in crumbs.keys():
        var c = crumbs[k]
        if is_instance_valid(c):
            c.queue_free()
    crumbs.clear()
    crumb_count = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if not walls[y][x]:
                var tile = Vector2(x, y)
                var c = Crumb.new()
                c.tile = tile
                add_child(c)
                c.position = tile_to_pos(tile)
                crumbs[tile] = c
                crumb_count += 1

func reset() -> void:
    # rebuild crumbs but keep walls
    _create_crumbs()
    call_deferred("update")

func is_open(tile:Vector2) -> bool:
    var x = int(tile.x)
    var y = int(tile.y)
    if x < 0 or y < 0 or x >= WIDTH or y >= HEIGHT:
        return false
    return not walls[y][x]

func tile_to_pos(tile:Vector2) -> Vector2:
    return offset + Vector2(tile.x * TILE_SIZE + TILE_SIZE / 2, tile.y * TILE_SIZE + TILE_SIZE / 2)

func eat_crumb(tile:Vector2) -> bool:
    # called when mouse arrives at tile
    if crumbs.has(tile):
        var c = crumbs[tile]
        if is_instance_valid(c):
            c.collect()
        crumbs.erase(tile)
        crumb_count = max(0, crumb_count - 1)
        return true
    return false

func get_crumb_count() -> int:
    return crumb_count

func _draw() -> void:
    # draw floor
    var floor_color = Color(0.9, 0.9, 0.9)
    var wall_color = Color(0.2, 0.2, 0.2)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            var pos = Vector2(offset.x + x * TILE_SIZE, offset.y + y * TILE_SIZE)
            var rect = Rect2(pos, Vector2(TILE_SIZE, TILE_SIZE))
            if walls[y][x]:
                draw_rect(rect, wall_color)
            else:
                draw_rect(rect, floor_color)
    # draw grid lines subtly
    for y in range(HEIGHT + 1):
        var start = Vector2(offset.x, offset.y + y * TILE_SIZE)
        var end = Vector2(offset.x + WIDTH * TILE_SIZE, offset.y + y * TILE_SIZE)
        draw_line(start, end, Color(0.7,0.7,0.7), 1)
    for x in range(WIDTH + 1):
        var start = Vector2(offset.x + x * TILE_SIZE, offset.y)
        var end = Vector2(offset.x + x * TILE_SIZE, offset.y + HEIGHT * TILE_SIZE)
        draw_line(start, end, Color(0.7,0.7,0.7), 1)

func _notification(what):
    if what == NOTIFICATION_ENTER_TREE:
        set_process(true)
    if what == NOTIFICATION_READY:
        call_deferred("update")
