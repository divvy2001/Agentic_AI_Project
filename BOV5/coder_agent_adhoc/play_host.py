"""Trusted standalone host for a visible, offline AppContainer play session.

Only the host reads its request and trusted sandbox implementation. The generated
game sees a separate staged game tree and a credential-free environment.
"""
import importlib.util
import json
import os
import re
from pathlib import Path
import sys
import traceback


def publish(file, value):
    target = Path(file)
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, target)


def import_error_text(output):
    # Same narrow AppContainer diagnostic exception as godot_runtime.run_godot:
    # the native token cannot query the volume filesystem type. Preserve raw
    # output, and remove only this exact two-line pair from error classification.
    benign = r'ERROR: Method/function failed\. Returning: ""\r?\n[ \t]+at: get_filesystem_type \(drivers/windows/dir_access_windows\.cpp:\d+\)\r?\n'
    return re.sub(benign, '', output)


def main():
    session = Path(sys.argv[1]).resolve()
    request = json.loads((session / 'request.json').read_text(encoding='utf-8'))
    status_file = session / 'launch.json'
    try:
        spec = importlib.util.spec_from_file_location('visible_play_sandbox', request['backend'])
        backend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend)
        if request['renderer'] == 'godot':
            imported = backend.launch(request['binary'],
                ['--headless', '--path', str(session / 'runtime/game'), '--editor', '--import', '--quit'],
                session / 'runtime', request['env'], timeout=60, output_limit=4 * 1024 * 1024)
            imported['error_check_output'] = import_error_text(imported.get('output', ''))
            publish(session / 'import.json', imported)
            if imported['returncode'] or imported['reason'] or re.search(r'(?im)SCRIPT ERROR:|Parse Error:|^ERROR:', imported['error_check_output']):
                publish(status_file, dict(status='failed', reason='godot_play_import_failed',
                                         evidence='import.json'))
                return 2
        def started(pid):
            publish(status_file, dict(status='started', pid=pid,
                    renderer=request['renderer'], sandbox='windows_appcontainer',
                    gameplay_acceptance='not_run'))
        result = backend.launch(request['binary'], request['args'], session / 'runtime',
                                request['env'], timeout=request['timeout'],
                                output_limit=4 * 1024 * 1024,
                                read_dirs=request['read_dirs'],
                                interactive=request['renderer'] == 'terminal', on_started=started)
        publish(session / 'exit.json', result)
        # Startup acknowledgement only means the real sandbox process resumed.
        # Never change it into gameplay PASS. Early failures remain in exit.json.
        return 0 if result['returncode'] == 0 and not result['reason'] else 2
    except Exception as exc:
        publish(status_file, dict(status='failed', reason=str(exc)))
        (session / 'host_error.log').write_text(traceback.format_exc(), encoding='utf-8')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
