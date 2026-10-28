import re
from coder_agent_adhoc.contracts import path

COMMON = """GODOT 4 PLAYBOOK
- Write game/project.godot with [application] run/main_scene="res://main.tscn". res:// IS the
  game/ directory: never write res://game/... paths. Godot is the runtime, not a pip package.
- Implement every Planner .gd/.tscn and keep the exact entry game/main.tscn. Godot 4 APIs only
  (await not yield, instantiate() not instance(), CharacterBody2D/3D not KinematicBody).
  Use Godot 4 syntax: @onready var / @export var, never the old "onready" / "export" keywords.
  Godot 3 names that break in Godot 4: update() -> queue_redraw(), linear_interpolate() -> lerp(), doubleclick -> double_click,
  instance() -> instantiate(), yield -> await. An inner class cannot read the outer script's
  variables: declare what it needs inside the inner class.
  If apply_patch fails twice on the same file, rewrite the whole file with write_file instead.
- .tscn comments use semicolons (;), NEVER unquoted #. A # can silently discard later
  properties/script bindings even if the engine exits 0. Keep script = ExtResource attached.
- .tscn files are square-bracket text, NOT XML. All [ext_resource]/[sub_resource] sections come
  before the first [node]. Minimal valid root scene:
    [gd_scene load_steps=2 format=3]
    [ext_resource type="Script" path="res://main.gd" id="1"]
    [node name="Main" type="Node2D"]
    script = ExtResource("1")
  Prefer such a small root scene plus nodes created in the planned scripts (add_child) over
  hand-serialized meshes, shapes or basis matrices. Reuse named children that a scene already
  declares; do not rely on get_child(index).
- Scene property values are serialized data, not GDScript: ClassName.new() is invalid in
  .tscn. Declare resources as [sub_resource type="..." id="..."] before all nodes and refer
  to them with SubResource("..."); or construct them in a planned .gd script.
- Input: create actions in _ready() with InputMap.add_action(name) (if missing) and
  InputEventKey.new() + physical_keycode = KEY_W + InputMap.action_add_event(name, event).
  Always add the required key bindings even if the action already exists: an existing action
  can have an empty event list. For new builds configure events in the planned controller's
  _ready(); avoid hand-serializing InputEvent objects in project.godot. For Repair preserve
  valid bindings, and fix missing/empty bindings in the existing controller when possible.
  Dictionaries such as {"type":"InputEventKey"} inside project.godot are NOT input events.
  Add letters and arrows where the Plan says so, plus real R/Escape events when planned.
- Window size: game/project.godot MUST have a [display] section setting
  window/size/viewport_width and window/size/viewport_height to the Planner resolution, plus
  window/stretch/mode="canvas_items". Without it Godot opens at 1152x648 and an 800x600 background
  leaves empty bands. Size backgrounds to the viewport (ColorRect full-rect anchors, or
  get_viewport_rect().size), never to a hard-coded size that differs from the resolution.
- Print WIN, LOSE and SCORE:X to stdout only on real state changes; show the same state in a
  CanvasLayer HUD with positioned Labels and control hints.
- For EVERY control the game handles, print() one line when it takes effect (e.g. DIRECTION up,
  RESTART, QUIT, JUMP), plus GAME OVER / WIN / LOSE on those events. List each control and its
  exact printed line in the play manual.
- If a scripted object reports only its native class and lacks declared signals/methods, inspect
  scene script bindings and parse diagnostics before renaming interfaces. A valid .gd on disk
  does not prove its PackedScene instance actually has that script attached.
- Typed GDScript: give explicit types to values read from Dictionaries/Arrays/Variants. Do not
  declare members that shadow built-ins (velocity, position, name, owner, scale, visible).
  Agree collection types at both caller and callee. Dictionary.keys() returns an untyped
  Array: append its values to a typed Array explicitly, or accept Array and cast its elements.
  Do not pass Array/Array[Vector2i] into an incompatible Array[Vector2] parameter.
- Restart: either reset existing nodes in place, or remove_child(old) BEFORE old.queue_free()
  when a replacement reuses its name; never keep references to freed nodes.
- argv=['syntax'] runs a headless --import; argv=['boot'] loads the main scene and requires
  10 simulated seconds at fixed 60 FPS. Fix delayed timer/signal errors as well as every SCRIPT ERROR / Parse Error even when the exit code is 0.
- Checks run in an offline Windows AppContainer on a copy of game/; .godot caches, .uid files
  and user:// stay in that copy. Never write them with tools; no plugins or native extensions."""

DIM_3D = """GODOT 3D NOTES
- Meshes: MeshInstance3D.mesh = BoxMesh/SphereMesh/PlaneMesh/CapsuleMesh.new(); colors through
  StandardMaterial3D in material_override. A PlaneMesh is visual only: a gravity-driven body
  needs a StaticBody3D floor with an enabled CollisionShape3D, matching layers/masks, and a
  spawn point above it. Bound arenas with collision walls or clamped X/Z including body size.
- Camera3D: place it off-axis (e.g. (0, 14, 12)) and call look_at(arena_center, Vector3.UP);
  look_at fails when the camera position is collinear with the up vector. Check that the
  player and goals are inside the view. Add a DirectionalLight3D.
- Use Area3D body_entered (connected explicitly) or real distance checks for pickups/goals."""

DIM_2D = """GODOT 2D NOTES
- Match the Plan's movement model: discrete grid/turn games can use Node2D state and one
  move per non-echo key press. Use CharacterBody2D/move_and_slide and collision shapes when
  physics is actually needed. Do not add gravity, inertia or held-key movement to a turn game.
- Draw procedural visuals with ColorRect/Polygon2D or _draw(); keep everything inside the
  Planner resolution, or follow the player with a Camera2D. Fit supplied textures using
  their validated dimensions; keep sprite origins and logical/world coordinates consistent.
- Choose ONE sprite anchor convention. A Sprite2D at a cell CENTER normally uses centered=true,
  offset=Vector2.ZERO. At a cell TOP-LEFT it can use centered=false, offset=Vector2.ZERO.
  If grid_to_pixel already adds half a tile, do not add another half-tile sprite offset.
  Review actual rendered bounds, not just a logical position variable."""


def playbook(p):
    dims = p['profile']['dimensions'].lower()
    parts = [COMMON]
    if '3d' in dims:
        parts.append(DIM_3D)
    elif '2d' in dims:
        parts.append(DIM_2D)
    return '\n'.join(parts)


def contract_check(p):
    project_file = path('game/project.godot', game=True)
    if not project_file.is_file():
        return 'missing_godot_project', 'Create game/project.godot with [application] run/main_scene="res://main.tscn".'
    project = project_file.read_text(encoding='utf-8')
    return project_text_problem(project) or window_size_problem(project, p)


def window_size_problem(project, p):
    """FIX (resolution): the window must match the Planner resolution, or backgrounds leave empty bands."""
    res = (p.get('architecture') or {}).get('resolution') or {}
    w, h = res.get('width'), res.get('height')
    if not w or not h:
        return None
    got_w = re.search(r'(?m)^\s*window/size/viewport_width\s*=\s*(\d+)', project)
    got_h = re.search(r'(?m)^\s*window/size/viewport_height\s*=\s*(\d+)', project)
    if not got_w or not got_h or int(got_w[1]) != int(w) or int(got_h[1]) != int(h):
        return ('godot_window_size_mismatch',
                f'game/project.godot must set the Planner resolution {w}x{h}: add a [display] section with '
                f'window/size/viewport_width={w}, window/size/viewport_height={h} and window/stretch/mode="canvas_items". '
                f'Godot otherwise opens at 1152x648 and backgrounds sized {w}x{h} leave empty bands.')
    return None


def project_text_problem(project):
    """Validate a proposed project file before an invalid input map reaches disk."""
    application = re.search(r'(?ms)^\[application\]\s*\n(.*?)(?=^\[|\Z)', project)
    configured = re.search(r'(?m)^\s*run/main_scene\s*=\s*"([^"\n]+)"', application[1]) if application else None
    if not configured or configured[1] != 'res://main.tscn':
        return ('project_main_scene_mismatch',
                'game/project.godot [application] must set run/main_scene="res://main.tscn". res:// already IS '
                'game/; res://game/main.tscn is incorrect. Actual: ' + (configured[1] if configured else 'missing'))
    if re.search(r'"events"\s*:\s*\[\s*\{', project):
        return ('invalid_godot_input_events',
                'InputMap events in project.godot must be InputEvent resources, not dictionaries. Remove dictionary '
                'events and configure InputEventKey.new() + physical_keycode + InputMap.action_add_event in the planned .gd source.')
    if re.search(r'(?m)^\s*\w+/(?:events|deadzone)\s*=', project):
        return ('invalid_godot_input_actions',
                'project.godot [input] action/events keys create actions literally named action/events, '
                'not action. Configure InputMap.add_action and InputEventKey in a planned script _ready(), '
                'or use a valid action dictionary with actual InputEvent resources. Existing empty actions still need bindings.')
    return None


def source_check(p):
    """Fast format checks for every planned scene before starting the engine."""
    scripts = []
    scenes = []
    for item in p['architecture']['files']:
        if item['path'].endswith(('.gd', '.tscn')) and path(item['path'], game=True).is_file():
            text = path(item['path'], game=True).read_text(encoding='utf-8')
            issue = resource_contract_problem(text, p)
            if issue:
                return issue
            if item['path'].endswith('.gd'):
                scripts.append(text)
            else:
                scenes.append(text)
            for reference in constant_resources(text):
                # Constant local resource references must exist; don't speculate
                # about dynamic paths. Resolve through the normal confined path API.
                try:
                    exists = path('game/' + reference[6:], game=True).is_file()
                except ValueError:
                    exists = False
                if not exists:
                    return ('godot_missing_resource', item['path'] + ' references missing ' + reference +
                            '. Use the exact Planner-promised filename and complete its implementation; do not add unplanned files.')
    substantive = []
    for code in scripts:
        rows = [s.strip() for s in re.sub(r'(?m)^\s*#.*$', '', code).splitlines() if s.strip()]
        substantive.extend(s for s in rows if not re.match(r'^(extends\b|class_name\b|func\s+_ready\s*\(|print\s*\(|pass\s*$)', s))
    graphical = re.search(r'type="(?:Sprite2D|AnimatedSprite2D|ColorRect|Label|Button|TextureRect|Polygon2D|Line2D|TileMap\w*|MeshInstance3D|CSG\w*|RichTextLabel|ProgressBar|Panel)"', '\n'.join(scenes))
    for f in p['architecture']['files']:
        if not f['path'].endswith('.tscn'):
            continue
        scene = path(f['path'], game=True)
        if not scene.is_file():
            continue
        text = scene.read_text(encoding='utf-8')
        uid_problem = scene_uid_problem(text, f['path'], p)
        if uid_problem:
            return uid_problem
        problem=scene_text_problem(text,f['path'])
        if problem:return problem
    requirements='\n'.join(r.get('text','')+' '+r.get('check','') for r in p['requirements'] if r.get('status')!='dropped')
    if re.search(r'(?i)\bWASD\b|arrow keys|keyboard controls|\bEscape\b|方向键|键盘移动',requirements):
        scripts=[]
        for item in p['architecture']['files']:
            if item['path'].endswith('.gd') and path(item['path'],game=True).is_file():
                scripts.append(re.sub(r'(?m)^\s*#.*$','',path(item['path'],game=True).read_text(encoding='utf-8')))
        code='\n'.join(scripts)
        if not re.search(r'\bInput\.|func\s+_(?:input|unhandled_input|unhandled_key_input|gui_input|shortcut_input)\b|\.connect\s*\(|func\s+_on_\w*(?:pressed|input|changed)',code):
            return ('godot_input_implementation_missing',
                    'Plan requires keyboard controls, but planned scripts have no input implementation. '
                    'An extends-only controller is not a repair: restore its planned game-state/input logic, '
                    'with real InputEventKey bindings. Read the controller and input configuration together.')
    if scenes and not substantive and not graphical:
        return ('godot_empty_game', 'Only a scene root and logging/pass stubs exist. No visible game or interactive logic was implemented. '
                'Implement the actual promised file purposes and Plan requirements; printing Game started is not a game.')
    return None


def scene_text_problem(text,name):
    """Reject known GDScript expressions in serialized scenes before writing."""
    quote = None
    escaped = False
    comment = False
    line = 1
    for char in text:
        if char == "\n":
            line += 1
            comment = False
        if comment:
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char == ';':
            comment = True
        elif char == '#':
            return ('godot_scene_comment', name + ':' + str(line) +
                    ': # is not a TSCN comment. Use ; comments outside quoted strings. '
                    'Godot can silently discard subsequent scene properties/script bindings and still exit 0. '
                    'Preserve actual node properties and script assignments; fix the scene, not signal names.')
    if re.search(r'(?m)^\s*\w+\s*=\s*(?:\w+\.new|preload|load)\s*\(',text) or re.search(r'(?m)^\[node\b[^\n]*\binstance\s*=\s*(?:preload|load)\s*\(',text):
        return ('godot_scene_format',name+': .tscn values cannot call ClassName.new(), preload() or load(). '
                'Use [ext_resource] + ExtResource("id") for scripts/scenes/textures and '
                '[sub_resource] + SubResource("id") for embedded resources; declare all before the first [node]. '
                'GDScript constructors/loading calls belong in planned .gd files.')
    if re.search(r'<(?:gd_scene|node|ext_resource|sub_resource)',text):
        return 'godot_scene_format',name+': Godot .tscn is square-bracket text, not XML. Use [gd_scene], [ext_resource] and [node] sections.'
    first_node=re.search(r'(?m)^\[node\b',text)
    if first_node and re.search(r'(?m)^\[(?:ext_resource|sub_resource)\b',text[first_node.start():]):
        return ('godot_scene_format',name+': All ext_resource and sub_resource sections must appear BEFORE the first [node] section. Prefer a minimal root scene and create nodes in the planned script.')
    return None


def constant_resources(text):
    text = re.sub(r'(?m)^\s*#.*$', '', text)
    if re.search(r'(?m)^\[(?:gd_scene|gd_resource)\b', text):
        return re.findall(r'(?m)^\[ext_resource\b[^\n]*\bpath\s*=\s*["\x27](res://[^"\x27\n]+)["\x27]', text)
    return re.findall(r'(?:\b(?:preload|load)\s*\(\s*|^\s*extends\s+)["\x27](res://[^"\x27\n]+)["\x27]', text, re.M)


def resource_contract_problem(text, p):
    """Constant references may target future promised files, never invented scenes."""
    promised = {f['path'] for f in p['architecture']['files']} | {'game/project.godot'}
    for reference in constant_resources(text):
        relative = 'game/' + reference[6:]
        if reference.endswith('/') or '%' in reference or '{' in reference:
            continue  # Directory/dynamic paths are resolved by the real engine.
        if relative in promised:
            continue
        try:
            supplied = relative.startswith('game/assets/') and path(relative, game=True).is_file()
        except ValueError:
            supplied = False
        if reference.startswith('res://game/'):
            return ('unplanned_godot_resource', reference + ' is wrong: res:// already IS the game/ folder. '
                    'Use ' + 'res://' + reference[len('res://game/'):] + ' instead (drop the game/ part).')
        if not supplied:
            return ('unplanned_godot_resource', reference + ' is not a Planner-promised file or supplied asset. '
                    'Do not invent a scene to change the architecture. Use the existing promised script/scene and its agreed interface.')
    return None


def scene_uid_problem(text, name, p):
    found = re.search(r'(?m)^\[gd_scene\b[^\n]*\buid="([^"\n]+)"', text)
    if not found:
        return None
    for item in p['architecture']['files']:
        other = item['path']
        if other == name or not other.endswith('.tscn') or not path(other, game=True).is_file():
            continue
        header = re.search(r'(?m)^\[gd_scene\b[^\n]*\buid="([^"\n]+)"', path(other, game=True).read_text(encoding='utf-8'))
        if header and header[1] == found[1]:
            return ('godot_duplicate_scene_uid', name + ' shares scene UID ' + found[1] + ' with ' + other +
                    '. Remove invented/reused UID headers and redundant ext_resource UIDs; let Godot assign real unique IDs. Keep resource paths and Planner filenames.')
    return None


def boot_check(p, result):
    # SceneTree-level evidence only: the main scene stayed loaded for 3 frames.
    if result.get('observed', {}).get('update_frames', 0) < 3:
        return 'godot_update_path_not_observed'
    return None


# FIX (godot3 names): Godot 3 API names that no longer exist in Godot 4.
# Checked when the coder saves a .gd file, so every old name is reported at once
# instead of Godot finding them one boot at a time.
GODOT3_NAMES = [
    (r'(?<![\w.])update\s*\(\s*\)', 'update()', 'queue_redraw()'),
    (r'\.linear_interpolate\s*\(', '.linear_interpolate()', '.lerp()'),
    (r'\.doubleclick\b', '.doubleclick', '.double_click'),
    (r'\.instance\s*\(\s*\)', '.instance()', '.instantiate()'),
    (r'\byield\s*\(', 'yield(...)', 'await'),
    (r'^\s*onready\s+var\b', 'onready var', '@onready var'),
    (r'^\s*export(\s*\(.*?\))?\s+var\b', 'export var', '@export var'),
    (r'\bKinematicBody(2D|3D)?\b', 'KinematicBody', 'CharacterBody2D/3D'),
    (r'\brand_range\s*\(', 'rand_range()', 'randf_range()'),
    (r'\bstepify\s*\(', 'stepify()', 'snapped()'),
    (r'\bdeg2rad\s*\(', 'deg2rad()', 'deg_to_rad()'),
    (r'\brad2deg\s*\(', 'rad2deg()', 'rad_to_deg()'),
    (r'\.empty\s*\(\s*\)', '.empty()', '.is_empty()'),
    (r'\bscancode\b', 'scancode', 'keycode / physical_keycode'),
    (r'\bBUTTON_(LEFT|RIGHT|MIDDLE)\b', 'BUTTON_LEFT', 'MOUSE_BUTTON_LEFT'),
    (r'\bOS\.get_ticks_msec\s*\(', 'OS.get_ticks_msec()', 'Time.get_ticks_msec()'),
    (r'\bOS\.set_window_title\s*\(', 'OS.set_window_title()', 'DisplayServer.window_set_title() or project setting'),
    (r'\bOS\.window_(size|fullscreen|position)\b', 'OS.window_*', 'DisplayServer.window_get/set_*'),
    (r'\.set_cell(v)?\s*\(\s*-?\d+\s*,\s*-?\d+\s*,', 'TileMap.set_cell(x, y, id)', 'set_cell(layer_or_coords, Vector2i(x, y), source_id, atlas_coords)'),
    (r'\.connect\s*\(\s*["\x27]\w+["\x27]\s*,\s*self\s*,', 'connect("signal", self, "method")', 'signal.connect(method)'),
]


def godot3_api_problem(text, name):
    code = re.sub(r'(?m)#.*$', '', text)          # ignore comments
    code = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)  # ignore string contents
    found = []
    for pattern, old, new in GODOT3_NAMES:
        if re.search(pattern, code, re.M) and f'{old} -> {new}' not in found:
            found.append(f'{old} -> {new}')
    if found:
        return ('godot3_api', name + ' uses Godot 3 names that do not exist in Godot 4: ' + '; '.join(found) +
                '. Replace ALL of them in this file, then save again.')
    return None
