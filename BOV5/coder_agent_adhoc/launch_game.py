"""Visible handoff after Coder readiness, separate from generation and smoke.

No model-supplied shell commands, no unrestricted fallback. A disposable game
copy runs inside the existing Windows AppContainer for at most two hours.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.contracts import path


def launch_game(renderer, entry_point, wait_seconds=30):
    if os.name != 'nt':
        raise OSError('visible_play_requires_windows')
    if renderer not in ('terminal', 'pygame', 'godot'):
        raise ValueError('unsupported_renderer')
    entry = path(entry_point, game=True)
    if not entry.is_file():
        raise FileNotFoundError('game_entry_missing')
    # Validate all paths before following/copying anything into the play session.
    files = []
    for item in C.GAME_DIR.rglob('*'):
        rel = item.relative_to(C.GAME_DIR)
        if any(p in ('.godot', '__pycache__', 'tests') for p in rel.parts):
            continue
        source = path('game/' + rel.as_posix(), game=True)
        if source.name == '.env' or source.suffix.lower() in ('.env', '.key', '.pem'):
            raise ValueError('secret_file_in_game_denied')
        if source.is_file():
            files.append((source, rel))
    binary = sys.executable
    if renderer == 'godot':
        from coder_agent_adhoc.godot_runtime import binary as godot_binary
        binary = godot_binary()
    session = C.ROOT / 'traces' / ('play-' + uuid.uuid4().hex)
    runtime = session / 'runtime'
    game = runtime / 'game'
    game.mkdir(parents=True)
    for source, rel in files:
        dest = game / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    module_dir = Path(__file__).resolve().parent
    if renderer == 'godot':
        # The visible game uses normal automatic imports, not a smoke observer
        # or --quit-after. Its imported cache lives only in this disposable copy.
        args = ['--path', str(game)]
        read_dirs = []
    else:
        shutil.copy2(module_dir / 'play_child.py', runtime / 'play_child.py')
        args = ['-I', '-B', str(runtime / 'play_child.py'), entry_point]
        read_dirs = [sys.prefix]
    names = ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT')
    env = {k: os.environ[k] for k in names if k in os.environ}
    env.update(PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1')
    request = dict(renderer=renderer, binary=binary, args=args, read_dirs=read_dirs,
                   env=env, timeout=7200, backend=str(module_dir / 'windows_sandbox.py'))
    (session / 'request.json').write_text(json.dumps(request, indent=2), encoding='utf-8')
    # The sandbox child owns the Terminal console; closing it must not kill the
    # trusted cleanup host. GUI renderers open their normal windows themselves.
    flags = subprocess.CREATE_NO_WINDOW
    with (session / 'host_stdout.log').open('wb') as output:
        host = subprocess.Popen([sys.executable, '-I', '-B', str(module_dir / 'play_host.py'), str(session)],
                                cwd=session, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                creationflags=flags, close_fds=True)
    status_file = session / 'launch.json'
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if status_file.is_file():
            status = json.loads(status_file.read_text(encoding='utf-8'))
            status['session_dir'] = session.relative_to(C.ROOT).as_posix()
            status['exit_record'] = (session / 'exit.json').relative_to(C.ROOT).as_posix()
            return status
        if host.poll() is not None:
            break
        time.sleep(.05)
    # Do not kill a native ACL transaction halfway through. A live host may be
    # waiting for another play session's runtime lock; acknowledge that honestly.
    return dict(status='pending' if host.poll() is None else 'failed',
                reason='visible_launch_acknowledgement_pending' if host.poll() is None else 'visible_launch_host_exited',
                host_pid=host.pid,
                session_dir=session.relative_to(C.ROOT).as_posix())


def finish_with_play(result, enabled=True):
    if result.get('status') != 'ready_for_testing':
        result['play_session'] = dict(status='not_run', reason='coder_not_ready')
    elif not enabled:
        result['play_session'] = dict(status='not_run', reason='disabled_by_caller')
    else:
        try:
            result['play_session'] = launch_game(result['renderer'], result['entry_point'])
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            result['play_session'] = dict(status='failed', reason=str(exc))
    if enabled and result.get('status') == 'ready_for_testing':
        play = result['play_session']
        print('[PLAY] ' + json.dumps(play, ensure_ascii=False))
    return result


def main():
    from coder_agent_adhoc.contracts import plan
    try:
        p = plan(mode='repair')
        validate_existing_game(p)
        result = launch_game(p['profile']['renderer'], p['architecture']['entry_point'])
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        result = dict(status='failed', reason=str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] in ('started', 'pending') else 2


def validate_existing_game(p):
    """Read-only preflight before a manual launch; never run an unfinished tree."""
    from coder_agent_adhoc import build_state
    from coder_agent_adhoc.run_context import digest
    from coder_agent_adhoc.gates import smoke
    from coder_agent_adhoc.godot_runtime import release_stage
    receipt_file = C.ROOT / 'traces/coder_result.json'
    if receipt_file.is_file():
        receipt = json.loads(receipt_file.read_text(encoding='utf-8'))
        same = (receipt.get('plan_sha256') == digest(C.PLAN_FILE.read_bytes())
                and receipt.get('game_sha256') == build_state.game_hashes())
        if same and receipt.get('status') != 'ready_for_testing':
            raise ValueError('last_build_not_ready: ' + str(receipt.get('reason')) +
                             '; resume Initial Build ' + str(receipt.get('attempt_id')))
    protected = {f.relative_to(C.ROOT).as_posix(): f.read_bytes() for folder in ('plans', 'game/assets', 'game/tests')
                 for f in (C.ROOT / folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    try:
        gates, evidence, reason = smoke(p, protected, set(), 'existing')
        output = dict(status='failed' if reason else 'passed', gates=gates, evidence=evidence, reason=reason)
        file = C.ROOT / 'traces/launch_check.json'
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
        if reason:
            raise ValueError('game_not_launchable: ' + reason + '; see traces/launch_check.json')
    finally:
        release_stage()


if __name__ == '__main__':
    raise SystemExit(main())
