"""Renderer presentation evidence, not gameplay grading or a second Validator."""
import json
import re
import shutil
import uuid
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.run_context import CURRENT


def expected(p):
    if p['profile']['renderer'] == 'terminal':
        return False
    text = ' '.join(r.get('text', '') + ' ' + r.get('check', '') for r in p['requirements'] if r.get('status') != 'dropped')
    text += ' ' + ' '.join(f.get('purpose', '') for f in p['architecture']['files'])
    return bool(re.search(r'(?i)\b(display|visible|screen|window|render\w*|sprite\w*|camera|hud|grid|board|ui|button\w*)\b|画面|界面|显示|棋盘', text))


DRIVER = '''extends SceneTree
func _initialize():
    call_deferred("probe")
func walk(n: Node) -> Array:
    var nodes: Array = [n]
    for child in n.get_children():
        nodes.append_array(walk(child))
    return nodes
func probe():
    if change_scene_to_file(str(ProjectSettings.get_setting("application/run/main_scene"))) != OK:
        push_error("Presentation scene load failed")
        quit(2)
        return
    var image: Image
    var colors: Dictionary = {}
    for sample in range(3):
        await create_timer(0.2).timeout
        await RenderingServer.frame_post_draw
        image = root.get_texture().get_image()
        if image == null or image.is_empty():
            push_error("Presentation image unavailable")
            quit(2)
            return
        colors.clear()
        for y in range(0,image.get_height(),maxi(1,image.get_height()/48)):
            for x in range(0,image.get_width(),maxi(1,image.get_width()/64)):
                colors[image.get_pixel(x,y).to_rgba32()] = true
        if colors.size() > 1:
            break
    var camera: Camera3D = root.get_camera_3d()
    var geometry: int = 0
    var in_view: int = 0
    var canvas: int = 0
    var labels: Array = []
    for node in walk(current_scene):
        if node is CanvasItem and node.is_visible_in_tree():
            canvas += 1
        if node is Label and node.is_visible_in_tree():
            labels.append(node.text)
        if node is GeometryInstance3D and node.is_visible_in_tree():
            geometry += 1
            if camera != null and camera.is_position_in_frustum(node.global_position):
                in_view += 1
    if image.save_png(__IMAGE_PATH__) != OK:
        push_error("Presentation evidence save failed")
        quit(2)
        return
    print("CODER_PRESENTATION:"+JSON.stringify({"colors":colors.size(),"canvas_items":canvas,"geometry":geometry,"geometry_in_view":in_view,"camera":camera != null,"labels":labels,"width":image.get_width(),"height":image.get_height()}))
    quit()
'''


def check(p):
    if not expected(p):
        return dict(status='not_run', reason='no_explicit_visual_requirement'), None
    if p['profile']['renderer'] != 'godot':
        # Pygame observes its actual presented surface in the Python child.
        return dict(status='not_run', reason='checked_in_renderer_boot'), None
    from coder_agent_adhoc import godot_runtime as G
    from coder_agent_adhoc.execution import child_env
    from coder_agent_adhoc.gates import command_failed
    stage, _ = G.stage_game()
    observer = stage / 'presentation_probe.gd'
    observer.write_text(DRIVER.replace('__IMAGE_PATH__', json.dumps((stage / 'presentation.png').as_posix())), encoding='utf-8')
    result = G.launch(G.binary(), ['--path', str(stage / 'game'), '--script', str(observer),
                     '--rendering-method', 'gl_compatibility'], stage, child_env(),
                     timeout=C.COMMAND_TIMEOUT, output_limit=C.OUTPUT_LIMIT)
    # Same exact native volume-query exception as normal Godot checks.
    benign = r'ERROR: Method/function failed\. Returning: ""\r?\n[ \t]+at: get_filesystem_type \(drivers/windows/dir_access_windows\.cpp:\d+\)\r?\n'
    result['error_check_output'] = re.sub(benign, '', result.get('output', ''))
    found = re.findall(r'CODER_PRESENTATION:(\{[^\n]*\})', result.get('output', ''))
    observed = json.loads(found[-1]) if found else {}
    reason = None
    if command_failed(result) or not observed:
        reason = 'presentation_probe_failed'
    elif '3d' in p['profile']['dimensions'].lower() and (not observed.get('camera') or not observed.get('geometry_in_view')):
        reason = 'presentation_3d_geometry_not_in_camera'
    elif observed.get('colors', 0) < 2:
        reason = 'presentation_uniform_frame'
    elif not observed.get('canvas_items') and not observed.get('geometry'):
        reason = 'presentation_no_visible_content'
    evidence = dict(status='failed' if reason else 'passed', reason=reason, observed=observed,
                    scope='Rendered startup frame only; input, WIN/LOSE and reset remain unverified',
                    command=result)
    image = stage / 'presentation.png'
    if image.is_file():
        ctx = CURRENT.get()
        target = C.ROOT / 'traces' / ('presentation-' + (ctx.attempt_id if ctx else uuid.uuid4().hex) + '.png')
        shutil.copy2(image, target)
        evidence['image_path'] = target.relative_to(C.ROOT).as_posix()
    return evidence, reason
