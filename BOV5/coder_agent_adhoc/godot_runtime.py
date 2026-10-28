"""Mirror current game into a credential-free native sandbox; never execute shared game in place."""
import atexit, hashlib, os, re, shutil, tempfile, time
from pathlib import Path
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.contracts import path
from coder_agent_adhoc.windows_sandbox import launch, SandboxUnavailable
from coder_agent_adhoc.run_context import CURRENT

_STAGES={}
_IMPORTED={}

def _cleanup():
    for root,stage,_ in list(_STAGES.values()):
        boundary=(root/'traces').resolve(); resolved=stage.resolve()
        if resolved.is_relative_to(boundary) and resolved.name.startswith('gd-runtime-'):
            shutil.rmtree(resolved,ignore_errors=True)
    _STAGES.clear()
    _IMPORTED.clear()
atexit.register(_cleanup)

def stage_game():
    root=C.ROOT.resolve(); ctx=CURRENT.get()
    key=(str(root),ctx.attempt_id if ctx else 'direct')
    if key not in _STAGES:
        (root/'traces').mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix='gd-runtime-',dir=root/'traces'))
        _STAGES[key]=(root,stage,set())
    _,stage,previous=_STAGES[key]
    game=stage/'game';game.mkdir(exist_ok=True)
    current=set(); hashes={}
    for f in C.GAME_DIR.rglob('*'):
        relative=f.relative_to(C.GAME_DIR)
        if any(x in relative.parts for x in ('.godot','__pycache__')):continue
        # Deny symlinks/junctions and traversal before copying any resource.
        source=path('game/'+relative.as_posix(),game=True)
        if not source.is_file(): continue
        if source.name=='.env' or source.suffix.lower() in ('.key','.pem'):
            raise SandboxUnavailable('secret_file_in_game_denied')
        dest=game/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists() or dest.read_bytes()!=source.read_bytes():shutil.copy2(source,dest)
        current.add(relative.as_posix());hashes[relative.as_posix()]=hashlib.sha256(source.read_bytes()).hexdigest()
    # Keep Godot-generated sidecars for authoritative source resources. PNG.import
    # is outside .godot/ and is required to resolve its imported Texture2D on boot.
    # Deleting it after --import makes valid supplied PNGs appear unloadable.
    # Sidecars for deleted/untrusted extra sources are still removed.
    extras={f.relative_to(game).as_posix() for f in game.rglob('*') if f.is_file()
            and '.godot' not in f.relative_to(game).parts and f.relative_to(game).as_posix() not in current
            and not (f.suffix in ('.uid','.import') and f.with_suffix('').relative_to(game).as_posix() in current)}
    for name in (previous-current)|extras:
        target=(game/name).resolve()
        if target.is_relative_to(game.resolve()) and target.is_file():target.unlink()
    _STAGES[key]=(root,stage,current)
    return stage,hashes

def release_stage():
    ctx=CURRENT.get(); key=(str(C.ROOT.resolve()),ctx.attempt_id if ctx else 'direct')
    item=_STAGES.pop(key,None)
    if item:
        root,stage,_=item
        _IMPORTED.pop(str(stage),None)
        if stage.resolve().parent==(root/'traces').resolve() and stage.name.startswith('gd-runtime-'):
            shutil.rmtree(stage,ignore_errors=True)

def binary():
    name=os.getenv('GODOT_BINARY') or shutil.which('godot') or shutil.which('godot4')
    if not name: raise FileNotFoundError('runtime_unavailable: godot')
    return str(Path(name).resolve())

def run_godot(action, timeout=None, visible=False):
    if os.name!='nt':raise SandboxUnavailable('runtime_unavailable: native Godot requires Windows AppContainer on this build')
    executable=binary()
    stage,hashes=stage_game()
    limit=timeout or C.COMMAND_TIMEOUT
    if action=='boot' and _IMPORTED.get(str(stage))!=hashes:
        # boot is a public standalone tool, not an assumption that the model
        # previously called syntax. Never diagnose missing import cache as a
        # generated-game texture failure. Both commands share the same deadline.
        started=time.monotonic()
        imported=run_godot('syntax',timeout=limit)
        if (imported.get('returncode') or imported.get('reason') or
                re.search(r'(?im)SCRIPT ERROR:|Parse Error:|^ERROR:',imported.get('error_check_output',''))):
            imported['phase']='import_before_boot'
            return imported
        limit=max(.01,limit-(time.monotonic()-started))
    args=['--path',str(stage/'game')]
    if not visible:args.insert(0,'--headless')
    if action=='syntax':args+=['--import']
    elif action=='boot':
        observer=stage/'startup_observer.gd'
        import json
        referenced=set()
        scripted=set()
        for source in C.GAME_DIR.rglob('*.gd'):
            if any(x in source.relative_to(C.GAME_DIR).parts for x in ('.godot','tests')):continue
            text=re.sub(r'(?m)^\s*#.*$','',source.read_text(encoding='utf-8'))
            referenced.update(re.findall(r'\b(?:is_action_pressed|is_action_just_pressed|is_action_released|is_action_just_released|get_action_strength|get_action_raw_strength)\s*\(\s*[\"\x27]([^\"\x27]+)[\"\x27]',text))
            for group in re.findall(r'\b(?:get_axis|get_vector)\s*\(([^)]+)\)',text):
                referenced.update(re.findall(r'[\"\x27]([^\"\x27]+)[\"\x27]',group))
            # Actions explicitly driven by script are allowed to have no physical binding.
            scripted.update(re.findall(r'Input\.action_(?:press|release)\s*\(\s*[\"\x27]([^\"\x27]+)[\"\x27]',text))
        referenced.difference_update(scripted)
        observer.write_text('''extends SceneTree
var observed_frames: int = 0
var bindings_checked: bool = false
var interaction_started: bool = false
var button_presses: Dictionary = {}
var required_actions: Array = '''+json.dumps(sorted(referenced))+'''
func _initialize():
    call_deferred("_start_scene")
func _start_scene():
    var error = change_scene_to_file(str(ProjectSettings.get_setting("application/run/main_scene")))
    if error != OK:
        push_error("Coder startup observer: scene load failed")
        quit(2)
        return
func _nodes(n: Node) -> Array:
    var out: Array = [n]
    for child in n.get_children():
        out.append_array(_nodes(child))
    return out
func _button_received(button_id: int):
    button_presses[button_id] = int(button_presses.get(button_id,0)) + 1
func _exercise_buttons():
    # Public renderer events only. Do not invoke game methods/signals or change state.
    await process_frame
    await process_frame
    var exercised: int = 0
    var world_points: int = 0
    for node in _nodes(current_scene):
        if not is_instance_valid(node) or not node is Button:
            continue
        if node.disabled or not node.is_visible_in_tree() or node.mouse_filter == Control.MOUSE_FILTER_IGNORE or node.get_viewport() != root:
            continue
        var caption: String = (node.text + " " + str(node.name)).to_lower()
        if "quit" in caption or "exit" in caption or "close" in caption or "escape" in caption:
            continue
        var pos: Vector2 = node.get_global_rect().get_center()
        if not Rect2(Vector2.ZERO,Vector2(root.size)).has_point(pos):
            continue
        var mouse_index: int = 0
        for index in range(1,10):
            if int(node.button_mask) & (1 << (index-1)):
                mouse_index = index
                break
        if mouse_index == 0:
            continue
        var button_id: int = node.get_instance_id()
        node.pressed.connect(_button_received.bind(button_id))
        var motion = InputEventMouseMotion.new()
        motion.position = pos
        motion.global_position = pos
        Input.parse_input_event(motion)
        await process_frame
        if not is_instance_valid(node) or node.disabled:
            continue
        var hovered: Control = root.gui_get_hovered_control()
        if hovered != null and hovered != node and not node.is_ancestor_of(hovered):
            continue # A separate modal/overlapping control intentionally owns this point.
        for down in [true, false]:
            var event = InputEventMouseButton.new()
            event.position = pos
            event.global_position = pos
            event.button_index = mouse_index
            event.pressed = down
            Input.parse_input_event(event)
            await process_frame
        exercised += 1
        if is_instance_valid(node) and not node.disabled and int(button_presses.get(button_id,0)) == 0:
            push_error("Coder input observer: enabled Button did not emit pressed after pointer input: " + str(node.get_path()) + "; inspect child Control mouse_filter and event propagation")
        # Continue a selected UI action into the world using ordinary pointer
        # events. Coordinates are bounded viewport samples, never private state.
        for fraction in [Vector2(0.5,0.5), Vector2(0.25,0.25)]:
            var target: Vector2 = Vector2(root.size) * fraction
            var move = InputEventMouseMotion.new()
            move.position = target
            move.global_position = target
            Input.parse_input_event(move)
            await process_frame
            for down in [true,false]:
                var click = InputEventMouseButton.new()
                click.position = target
                click.global_position = target
                click.button_index = MOUSE_BUTTON_LEFT
                click.pressed = down
                Input.parse_input_event(click)
                await process_frame
            world_points += 1
        if exercised >= 3:
            break
    print("CODER_GODOT_OBSERVED:button_events=" + str(exercised))
    print("CODER_GODOT_OBSERVED:world_points=" + str(world_points))
    var confirmed: int = 0
    for value in button_presses.values():
        confirmed += int(value)
    print("CODER_GODOT_OBSERVED:button_presses=" + str(confirmed))
func _check_bindings():
    for action_name in required_actions:
        if not InputMap.has_action(action_name):
            push_error("Coder startup input action missing: " + action_name)
            quit(2)
            return
        if InputMap.action_get_events(action_name).is_empty():
            push_error("Coder startup input action has no bound events: " + action_name + "; configure InputEventKey bindings even when the action already exists")
            quit(2)
            return
    bindings_checked = true
func _process(_delta):
    if not bindings_checked and current_scene != null and is_instance_valid(current_scene) and current_scene.is_node_ready():
        _check_bindings()
        if not interaction_started:
            interaction_started = true
            _exercise_buttons()
    if bindings_checked and current_scene != null and is_instance_valid(current_scene):
        observed_frames += 1
        if observed_frames == 3:
            print("CODER_GODOT_OBSERVED:update_frames=3")
        if observed_frames == 600:
            print("CODER_GODOT_OBSERVED:simulation_frames=600;fixed_fps=60")
    return false
''',encoding='utf-8')
        args+=['--script',str(observer),'--fixed-fps','60','--quit-after','660']
    elif action=='play' and visible:args+=['--rendering-method','gl_compatibility']
    else:raise ValueError('godot_action_not_allowed')
    from coder_agent_adhoc.execution import child_env
    result=launch(executable,args,stage,child_env(),timeout=limit,output_limit=C.OUTPUT_LIMIT)
    # AppContainer denies volume-root introspection. This exact engine diagnostic is
    # not a script/resource/import failure; keep raw output and explicitly record it.
    benign=r'ERROR: Method/function failed\. Returning: ""\r?\n[ \t]+at: get_filesystem_type \(drivers/windows/dir_access_windows\.cpp:\d+\)\r?\n'
    result['nonfatal_engine_diagnostics']=re.findall(benign,result['output'])
    result['error_check_output']=re.sub(benign,'',result['output'])
    result['observed']={'update_frames':3 if 'CODER_GODOT_OBSERVED:update_frames=3' in result['output'] else 0}
    if action=='boot':
        complete='CODER_GODOT_OBSERVED:simulation_frames=600;fixed_fps=60' in result['output']
        result['observed'].update(simulation_frames=600 if complete else 0,fixed_fps=60,
                                button_events=int((re.findall(r'CODER_GODOT_OBSERVED:button_events=(\d+)',result['output']) or ['0'])[-1]),
                                button_presses=int((re.findall(r'CODER_GODOT_OBSERVED:button_presses=(\d+)',result['output']) or ['0'])[-1]),
                                world_points=int((re.findall(r'CODER_GODOT_OBSERVED:world_points=(\d+)',result['output']) or ['0'])[-1]),
                                scope='10 simulated seconds; button_events counts attempts, button_presses confirms actual native pressed callbacks; 2 world clicks per selection; no semantic gameplay or OS input proof')
        if not complete and result['observed']['update_frames'] and not result.get('reason'):
            result['reason']='godot_observation_incomplete'
    for name,digest in hashes.items():
        f=stage/'game'/name
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=digest:
            result.update(reason='runtime_modified_source',returncode=125)
            break
    if (action=='syntax' and not result.get('returncode') and not result.get('reason') and
            not re.search(r'(?im)SCRIPT ERROR:|Parse Error:|^ERROR:',result['error_check_output'])):
        _IMPORTED[str(stage)]=hashes
    return result
