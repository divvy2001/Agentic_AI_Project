"""Coder-view validation, confined paths and current-task assets. No upstream writes."""
import json
import sys
from pathlib import Path, PureWindowsPath
from packaging.requirements import Requirement, InvalidRequirement
from coder_agent_adhoc.configuration import config as C

def path(value, game=False):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError('invalid_path')
    p = Path(value)
    if p.is_absolute() or PureWindowsPath(value).drive or '..' in p.parts or ':' in value:
        raise ValueError('unsafe_path')
    resolved = (C.ROOT / p).resolve()
    boundary = (C.ROOT / 'game').resolve() if game else C.ROOT.resolve()
    if not resolved.is_relative_to(boundary) or (game and p.parts[0] != 'game'):
        raise ValueError('path_outside_allowed_root')
    # Resolve every component; reject symlinks/junctions even when target is local.
    for parent in [C.ROOT / p, *(C.ROOT / p).parents]:
        if parent == C.ROOT.parent: break
        if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
            raise ValueError('linked_path_denied')
    return resolved

def dependency_name(dep):
    """Normalized distribution name of a Planner dependency such as 'pygame>=2.5'."""
    try: return Requirement(dep).name.lower().replace('_','-')
    except InvalidRequirement: raise ValueError('invalid_dependency_requirement: '+str(dep)) from None


def missing_dependencies(p):
    """Distributions the Plan needs that are not installed in this interpreter."""
    import importlib.metadata
    missing=[]
    for dep in p['architecture']['dependencies']:
        name=dependency_name(dep)
        try: importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: missing.append(name)
    return missing


def file_contract(p, mode='initial_build'):
    """Current Planner rules, with explicit existing-project Repair exceptions.

    No file-count ceiling exists upstream. Never rewrite the supplied Plan.
    """
    if mode not in ('initial_build', 'repair'):
        raise ValueError('invalid_mode')
    a=p['architecture']; renderer=p['profile']['renderer']; files=[f['path'] for f in a['files']]
    warnings=[]
    for name in files:
        if (not name.startswith('game/') or name.endswith('/') or Path(name).as_posix()!=name):
            raise ValueError('noncanonical_game_file_path')
    if files[0]!='game/__init__.py':
        if mode=='repair':
            warnings.append('legacy_repair_missing_package_marker' if 'game/__init__.py' not in files
                            else 'legacy_repair_package_marker_not_first')
        else:
            raise ValueError('package_marker_must_be_first')
    dependencies=[]
    for dep in a['dependencies']:
        name=dependency_name(dep)
        if name in sys.stdlib_module_names: raise ValueError('stdlib_not_dependency: '+name)
        dependencies.append(name)
    if renderer=='godot':
        if dependencies: raise ValueError('godot_dependencies_must_be_empty')
        if any(name.endswith('.py') and name!='game/__init__.py' for name in files):
            raise ValueError('godot_logic_must_be_gdscript')
    if renderer=='pygame' and 'pygame' not in dependencies:
        raise ValueError('pygame_dependency_required')
    resolution=a.get('resolution'); fps=a.get('fps')
    if renderer=='terminal':
        # Planner Prompt asks for null; extra render settings do not change a text game.
        if resolution is not None or fps is not None:
            warnings.append('terminal_render_settings_ignored')
    elif (not isinstance(resolution,dict) or set(resolution)!={'width','height'} or
          any(type(resolution.get(k)) is not int or resolution[k]<100 for k in ('width','height')) or
          (fps is not None and (type(fps) is not int or not 1<=fps<=240))):
        raise ValueError('graphical_resolution_and_fps_required')
    elif fps is None:
        warnings.append('graphical_fps_unspecified_using_planner_default_60')
    return warnings


def render_settings(p):
    """Planner-documented FPS default, without rewriting the immutable Plan."""
    if p['profile']['renderer'] == 'terminal': return None
    return dict(resolution=p['architecture'].get('resolution'),
                fps=p['architecture'].get('fps') if p['architecture'].get('fps') is not None else 60)


def asset_quality_warnings(p, current_assets):
    """Read-only diagnostics; visual acceptance stays separate from file validity.

    Do not remove backgrounds, rewrite upstream PNGs or silently replace sprites.
    """
    import re
    from PIL import Image
    requested = {a['id']: a for a in p['architecture']['assets'].get('sprites', [])}
    warnings = []
    for asset in current_assets:
        description = requested.get(asset['id'], {}).get('description', '')
        if not re.search(r'transparent|透明', description, re.I): continue
        f = path(asset['path'], game=True)
        if f.suffix.lower() != '.png': continue
        with Image.open(f) as im:
            if im.convert('RGBA').getchannel('A').getextrema()[0] == 255:
                warnings.append(dict(asset_id=asset['id'], path=asset['path'],
                                     issue='transparent_requested_but_image_fully_opaque'))
    return warnings


def plan(mode=None):
    """Parse a mode-neutral coder view; agent entrypoints supply their mode policy.

    Runtime/asset readers also use this function for existing projects. They do
    not imply a fresh Build. Strict policy always runs at each agent entrypoint.
    """
    p = json.loads(C.PLAN_FILE.read_text(encoding='utf-8'))
    if not isinstance(p,dict): raise ValueError('plan_not_an_object')
    for key in ('profile','architecture'):
        if not isinstance(p.get(key),dict): raise ValueError('invalid_'+key)
    a=p['architecture']
    if not isinstance(a.get('assets'),dict): raise ValueError('invalid_assets')
    if not isinstance(a.get('files'),list) or not all(isinstance(f,dict) for f in a['files']): raise ValueError('invalid_files')
    if not isinstance(p.get('requirements'),list) or not all(isinstance(r,dict) for r in p['requirements']): raise ValueError('invalid_requirements')
    if not isinstance(a['assets'].get('sprites',[]),list) or not all(isinstance(s,dict) for s in a['assets'].get('sprites',[])): raise ValueError('invalid_sprites')
    if p['status'] not in ('success', 'fallback'): raise ValueError('invalid_plan_status')
    if not isinstance(p['game_title'],str) or not p['game_title'].strip(): raise ValueError('missing_title')
    profile = p['profile']
    for k in ('genre','renderer','dimensions','pace'):
        if not isinstance(profile[k],str) or not profile[k]: raise ValueError('invalid_profile_field')
    if profile['renderer'] not in ('terminal','pygame','godot'): raise ValueError('invalid_renderer')
    if not isinstance(profile['players'],int) or isinstance(profile['players'],bool) or profile['players'] < 1: raise ValueError('invalid_players')
    a = p['architecture']
    if not isinstance(a['requires_input'], bool): raise ValueError('invalid_requires_input')
    if not isinstance(a['dependencies'],list) or not all(isinstance(x,str) and x for x in a['dependencies']): raise ValueError('invalid_dependencies')
    if not isinstance(p['unmapped'],list) or not isinstance(p['requirements'],list) or not p['requirements']: raise ValueError('invalid_requirements')
    for r in p['requirements']:
        for k in ('text','priority','status','check','quote'):
            if not isinstance(r[k],str): raise ValueError('invalid_requirement')
        if r['priority'] not in ('core','secondary'): raise ValueError('invalid_priority')
        if r['status'] not in ('full','approximated','dropped'): raise ValueError('invalid_requirement_status')
        if not isinstance(r['milestone'],int) or isinstance(r['milestone'],bool) or r['milestone']<1: raise ValueError('invalid_milestone')
    if not a['files']: raise ValueError('empty_files')
    files=[]
    for f in a['files']:
        path(f['path'],game=True)
        if not isinstance(f['purpose'],str): raise ValueError('invalid_file_purpose')
        files.append(f['path'])
    if len(set(files)) != len(files) or a['entry_point'] not in files: raise ValueError('invalid_entry_point')
    suffix='.tscn' if profile['renderer']=='godot' else '.py'
    if not a['entry_point'].endswith(suffix): raise ValueError('wrong_entry_extension')
    if profile['renderer']=='godot' and a['entry_point']!='game/main.tscn': raise ValueError('wrong_godot_entry')
    if a['assets']['strategy'] not in ('none','procedural','ai_art'): raise ValueError('invalid_asset_strategy')
    for u in p['unmapped']:
        if not isinstance(u,dict) or not all(isinstance(u.get(k),str) for k in ('quote','handling')): raise ValueError('invalid_unmapped')
    for sprite in a['assets'].get('sprites',[]):
        if not isinstance(sprite.get('id'),str): raise ValueError('invalid_sprite_id')
        for k in ('width','height'):
            if not isinstance(sprite.get(k),int) or isinstance(sprite[k],bool) or not 16<=sprite[k]<=512: raise ValueError('invalid_sprite_dimensions')
    if mode is not None:file_contract(p,mode)
    return p

def assets(p):
    strategy=p['architecture']['assets']['strategy']
    if strategy=='none': return []
    try:
        m=json.loads(C.ASSET_MANIFEST_FILE.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        if strategy=='procedural': return []
        raise ValueError('asset_missing: manifest')
    if not isinstance(m,dict):
        if strategy=='procedural': return []
        raise ValueError('asset_missing: manifest_not_an_object')
    if m.get('task_id')!=p['game_title'] or m.get('framework')!=p['profile']['renderer']:
        if strategy=='procedural': return []
        raise ValueError('asset_missing: stale_manifest')
    try:
        entries=m['assets']
        if not isinstance(entries,list) or not all(isinstance(a,dict) and isinstance(a.get('id'),str) for a in entries):
            raise ValueError('invalid_asset_entries')
        by_id={a['id']:a for a in entries}
        if len(by_id)!=len(entries): raise ValueError('duplicate_id')
        requested=p['architecture']['assets'].get('sprites',[])
        required={a['id'] for a in entries if a.get('required')} | ({a['id'] for a in requested} if strategy=='ai_art' else set())
        def checked(aid):
            a=by_id[aid]
            if a.get('generation_status')!='generated' or a.get('validation_status')!='passed': raise ValueError('asset_status')
            f=path(a['path'],game=True)
            if not f.is_file(): raise ValueError('asset_file_missing')
            if f.suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
                from PIL import Image
                with Image.open(f) as im:
                    im.verify()
                with Image.open(f) as im: size=im.size
                wanted=next((x for x in requested if x['id']==aid),a)
                if wanted.get('width') and size!=(wanted['width'],wanted['height']): raise ValueError('asset_dimensions')
            return a
        valid=[checked(aid) for aid in sorted(required)]
        for aid in by_id.keys()-required:
            try: valid.append(checked(aid))
            except (KeyError,TypeError,OSError,ValueError): pass
        return valid
    except (KeyError,TypeError,OSError,ValueError) as exc:
        raise ValueError('asset_missing: '+str(exc)) from exc
