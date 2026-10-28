"""Mandatory T1/T2/T3 startup checks, independent of model completion claims."""
import json
import re
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.contracts import path, assets, missing_dependencies
from coder_agent_adhoc.execution import run_action
from coder_agent_adhoc.adapters import adapter

ERROR_PATTERN = re.compile(r'(?im)(SCRIPT ERROR:|Parse Error:|^ERROR:|Traceback \(most recent)')


def command_failed(result):
    """True when an engine/python run failed, even with exit code 0."""
    return bool(result.get('returncode') or result.get('reason') or
                ERROR_PATTERN.search(result.get('error_check_output', result.get('output', ''))))


def file_inventory(p):
    """Count planned outputs separately from assets, tests and engine artifacts."""
    promised = {f['path'] for f in p['architecture']['files']}
    godot = p['profile']['renderer'] == 'godot'
    result = dict(promised_count=len(promised), delivered_promised=[], missing=[],
                  engine_supplements=[], assets=[], protected_tests=[], runtime_artifacts=[], unplanned=[])
    observed = set()
    if C.GAME_DIR.is_dir():
        for f in sorted(C.GAME_DIR.rglob('*')):
            name = f.relative_to(C.ROOT).as_posix()
            if not path(name, game=True).is_file():
                continue
            observed.add(name)
            parts = f.relative_to(C.GAME_DIR).parts
            if name in promised:
                result['delivered_promised'].append(name)
            elif name.startswith('game/assets/'):
                result['assets'].append(name)
            elif name.startswith('game/tests/'):
                result['protected_tests'].append(name)
            elif (any(x in ('.godot', '__pycache__') for x in parts) or
                  (godot and f.suffix == '.uid' and f.with_suffix('').relative_to(C.ROOT).as_posix() in promised)):
                result['runtime_artifacts'].append(name)
            elif godot and name == 'game/project.godot':
                result['engine_supplements'].append(name)
            else:
                result['unplanned'].append(name)
    result['missing'] = sorted(promised - observed)
    result['delivered_promised_count'] = len(result['delivered_promised'])
    return result


def _changed(protected):
    return next((name for name, content in protected.items()
                 if not path(name).is_file() or path(name).read_bytes() != content), None)


def smoke(p, protected, written, mode, require_manual=True):
    """Run T1 (files/contract), T2 (syntax/import) and T3 (bounded boot).

    Returns (gates, evidence, reason); reason is None only when every gate passed
    and a valid play manual exists. This is startup evidence, never gameplay PASS.
    """
    gates = dict(plan_and_files='not_run', syntax_or_import='not_run', boot='not_run')
    evidence = []
    renderer = p['profile']['renderer']
    engine = adapter(renderer)
    try:
        changed = _changed(protected)
        if changed:
            raise ValueError('protected_input_changed: ' + changed)
        files = [x['path'] for x in p['architecture']['files']]
        for name in files:
            if not path(name, game=True).is_file():
                raise ValueError('missing_promised_file: ' + name)
        inventory = file_inventory(p)
        if mode == 'initial_build' and inventory['unplanned']:
            raise ValueError('unplanned_game_file: ' + inventory['unplanned'][0])
        if mode == 'initial_build' and not set(files) <= written:
            raise ValueError('initial_build_missing_fresh_outputs')
        assets(p)
        problem = engine.contract_check(p)
        if problem:
            evidence.append(dict(returncode=1, reason=problem[0], seconds=0, output=problem[1]))
            raise ValueError(problem[0])
        missing = missing_dependencies(p)
        if missing:
            raise FileNotFoundError('runtime_unavailable: ' + ', '.join(missing))
        gates['plan_and_files'] = 'passed'

        problem = engine.source_check(p)
        if problem:
            gates['syntax_or_import'] = 'failed'
            evidence.append(dict(returncode=1, reason=problem[0], seconds=0, output=problem[1]))
            return gates, evidence, problem[0]
        source_before = {name: path(name, game=True).read_bytes() for name in files}
        for action, key in (('syntax', 'syntax_or_import'), ('boot', 'boot')):
            r = run_action(p, action)
            evidence.append(r)
            if command_failed(r):
                gates[key] = 'failed'
                if r.get('reason') and 'runtime_unavailable' in r['reason']:
                    return gates, evidence, r['reason']
                return gates, evidence, action + '_failed'
            if action == 'boot':
                reason = engine.boot_check(p, r)
                if reason:
                    gates[key] = 'failed'
                    return gates, evidence, reason
            gates[key] = 'passed'
        from coder_agent_adhoc.presentation import check as check_presentation
        presentation, problem = check_presentation(p)
        if presentation['status'] != 'not_run':
            if presentation.get('command'):
                evidence.append(presentation['command'])
            evidence.append(dict(presentation=presentation, returncode=1 if problem else 0,
                                 reason=problem, output=json.dumps({k: v for k, v in presentation.items() if k != 'command'}, ensure_ascii=False)))
        if problem:
            gates['boot'] = 'failed'
            return gates, evidence, problem
        changed = _changed(protected)
        if changed:
            gates['boot'] = 'failed'
            return gates, evidence, 'protected_input_changed: ' + changed
        if any(not path(name, game=True).is_file() or path(name, game=True).read_bytes() != content
               for name, content in source_before.items()):
            gates['boot'] = 'failed'
            return gates, evidence, 'runtime_modified_source'
        if not require_manual:
            return gates, evidence, None
        if mode == 'initial_build' and 'plans/play_manual.json' not in written:
            return gates, evidence, 'fresh_play_manual_required'
        manual = path('plans/play_manual.json')
        if not manual.is_file():
            return gates, evidence, 'play_manual_missing'
        m = json.loads(manual.read_text(encoding='utf-8'))
        if (not isinstance(m, dict) or set(m) != {'test_input', 'expected_win_output', 'expected_lose_output', 'notes'}
                or not all(isinstance(x, str) for x in m.values())):
            return gates, evidence, 'invalid_play_manual'
        return gates, evidence, None
    except FileNotFoundError as exc:
        return gates, evidence, str(exc)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        if gates['plan_and_files'] == 'not_run':
            gates['plan_and_files'] = 'failed'
        return gates, evidence, str(exc)
