"""Fixed check templates: credential-free child environment, sandboxed runtimes only."""
import os
import re
from coder_agent_adhoc.configuration import config as C

# Prose words that mark test_input_example as instructions rather than literal stdin.
PROSE = re.compile(r'(?i)\b(press|click|type|then|enter|repeat|until)\b|按下|输入|点击|然后')


def child_env():
    """Minimal environment for game processes: no keys, private HOME, dummy SDL."""
    names = ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'COMSPEC', 'LANG', 'LC_ALL')
    env = {k: os.environ[k] for k in names if k in os.environ}
    home = C.ROOT / 'traces/runtime_home'
    for folder in (home, home / 'AppData/Roaming', home / 'AppData/Local'):
        folder.mkdir(parents=True, exist_ok=True)
    env.update(USERPROFILE=str(home), HOME=str(home), APPDATA=str(home / 'AppData/Roaming'),
               LOCALAPPDATA=str(home / 'AppData/Local'))
    env.update(PYTHONPATH=str(C.ROOT), PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
               SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    return env


def stdin_sample(p):
    """Literal newline-separated stdin from test_input_example, never prose instructions."""
    example = p['architecture'].get('test_input_example')
    if not isinstance(example, str) or not ('\n' in example or '\\n' in example):
        return ''
    candidate = example.replace('\\n', '\n')
    lines = candidate.splitlines()
    if len(candidate) <= 8192 and all(len(line) <= 80 and len(line.split()) <= 4 and not PROSE.search(line)
                                      for line in lines):
        return candidate
    return ''


def run_action(p, action):
    """Run the fixed 'syntax' or 'boot' template for the Plan's renderer."""
    if action not in ('syntax', 'boot'):
        raise ValueError('command_not_allowed')
    from coder_agent_adhoc.windows_sandbox import SandboxUnavailable
    if p['profile']['renderer'] == 'godot':
        from coder_agent_adhoc.godot_runtime import run_godot
        try:
            return run_godot(action)
        except SandboxUnavailable as exc:
            raise FileNotFoundError('runtime_unavailable: sandbox: ' + str(exc)) from exc
    stdin = stdin_sample(p) if p['profile']['renderer'] == 'terminal' else ''
    from coder_agent_adhoc.python_runtime import run_python
    try:
        return run_python(p, action, stdin, bool(stdin))
    except SandboxUnavailable as exc:
        raise FileNotFoundError('runtime_unavailable: sandbox: ' + str(exc)) from exc
