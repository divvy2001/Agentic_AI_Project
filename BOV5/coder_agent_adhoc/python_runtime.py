"""Run Python games only in a disposable, credential-free Windows AppContainer."""
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.contracts import path
from coder_agent_adhoc.windows_sandbox import launch, SandboxUnavailable


def run_python(p, action, stdin='', has_sample=False):
    if os.name != 'nt':
        raise SandboxUnavailable('Python native isolation requires Windows on this build')
    from coder_agent_adhoc.execution import child_env
    parent=path('traces'); parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='py-runtime-',dir=parent) as td:
        stage=Path(td); game=stage/'game'; game.mkdir()
        before={}
        for item in C.GAME_DIR.rglob('*'):
            relative=item.relative_to(C.GAME_DIR)
            if any(part in ('.godot','__pycache__') for part in relative.parts): continue
            source=path('game/'+relative.as_posix(),game=True)
            if not source.is_file(): continue
            if source.name=='.env' or source.suffix.lower() in ('.env','.key','.pem'):
                raise SandboxUnavailable('secret_file_in_game_denied')
            dest=game/relative; dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,dest)
            before[relative.as_posix()]=hashlib.sha256(source.read_bytes()).hexdigest()
        shutil.copy2(Path(__file__).with_name('smoke_child.py'),stage/'smoke_child.py')
        env=child_env()
        env.update(CODER_HAS_STDIN_SAMPLE='1' if has_sample else '0',
                   CODER_RUNTIME_READ_ROOTS=str(Path(sys.prefix).resolve()))
        # -I ignores inherited Python search paths and user site customizations.
        args=['-I','-B',str(stage/'smoke_child.py'),p['profile']['renderer'],p['architecture']['entry_point'],action]
        result=launch(sys.executable,args,stage,env,timeout=C.COMMAND_TIMEOUT,
                      output_limit=C.OUTPUT_LIMIT,read_dirs=(sys.prefix,),stdin=stdin)
        if 'Fatal Python error:' in result['output'] or 'Python path configuration:' in result['output']:
            result.update(reason='runtime_unavailable: python_initialization',returncode=125)
        for name,digest in before.items():
            item=game/name
            if not item.is_file() or hashlib.sha256(item.read_bytes()).hexdigest()!=digest:
                result.update(reason='runtime_modified_source',returncode=125)
                break
        # Do not return stale paths to disposable staging directories.
        result['runtime']=dict(python=sys.version.split()[0],executable=sys.executable,
                               stdin_source='plan_sample' if has_sample else 'observe_wait')
        return result
