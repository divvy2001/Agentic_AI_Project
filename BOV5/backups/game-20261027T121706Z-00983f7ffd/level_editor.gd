extends Node2D
class_name LevelEditor

const WIDTH := 15
const HEIGHT := 15
const TILE_SIZE := 32

var walls := []
var offset := Vector2.ZERO
var preview_node := null

func _ready() -> void:
    var grid_px = Vector2(WIDTH * TILE_SIZE, HEIGHT * TILE_SIZE)
    offset = Vector2((800 - grid_px.x) / 2, (600 - grid_px.y) / 2)
    # initialize walls as 0 (open)
    walls = []
    for y in range(HEIGHT):
        var row := []
        for x in range(WIDTH):
            row.append(0)
        walls.append(row)
    set_process_input(true)
    queue_redraw()
    # instructions label
    var lbl = Label.new()
    lbl.text = "Click to toggle walls. Press P to preview/stop preview."
    add_child(lbl)
    lbl.position = Vector2(10, 10)

func _input(event) -> void:
    if event is InputEventMouseButton and event.pressed and not event.double_click:
        var mp = get_local_mouse_position()
        var local = mp - offset
        var tx = int(local.x / TILE_SIZE)
        var ty = int(local.y / TILE_SIZE)
        if tx >= 0 and ty >= 0 and tx < WIDTH and ty < HEIGHT:
            walls[ty][tx] = 1 - int(walls[ty][tx])
            queue_redraw()
    if event is InputEventKey and event.pressed and not event.echo:
        if event.physical_keycode == KEY_P:
            # toggle preview
            if preview_node and is_instance_valid(preview_node):
                preview_node.queue_free()
                preview_node = null
            else:
                print("PREVIEW")
                var packed = load("res://main.tscn")
                if packed:
                    preview_node = packed.instantiate()
                    add_child(preview_node)
                    # convert walls (0/1) to layout array of ints
                    var layout := []
                    for y in range(HEIGHT):
                        var row := []
                        for x in range(WIDTH):
                            row.append(int(walls[y][x]))
                        layout.append(row)
                    preview_node.call_deferred("set_layout", layout)
        elif event.physical_keycode == KEY_ESCAPE:
            # stop preview if any
            if preview_node and is_instance_valid(preview_node):
                preview_node.queue_free()
                preview_node = null

func _draw() -> void:
    # draw grid and walls
    for y in range(HEIGHT):
        for x in range(WIDTH):
            var pos = Vector2(offset.x + x * TILE_SIZE, offset.y + y * TILE_SIZE)
            var rect = Rect2(pos, Vector2(TILE_SIZE, TILE_SIZE))
            if int(walls[y][x]) == 1:
                draw_rect(rect, Color(0.2,0.2,0.2))
            else:
                draw_rect(rect, Color(0.95,0.95,0.95))
    # grid lines
    for y in range(HEIGHT + 1):
        var start = Vector2(offset.x, offset.y + y * TILE_SIZE)
        var end = Vector2(offset.x + WIDTH * TILE_SIZE, offset.y + y * TILE_SIZE)
        draw_line(start, end, Color(0.7,0.7,0.7), 1)
    for x in range(WIDTH + 1):
        var start = Vector2(offset.x + x * TILE_SIZE, offset.y)
        var end = Vector2(offset.x + x * TILE_SIZE, offset.y + HEIGHT * TILE_SIZE)
        draw_line(start, end, Color(0.7,0.7,0.7), 1)

func get_layout() -> Array:
    var layout := []
    for y in range(HEIGHT):
        var row := []
        for x in range(WIDTH):
            row.append(int(walls[y][x]))
        layout.append(row)
    return layout
