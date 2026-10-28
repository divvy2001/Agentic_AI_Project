"""Native isolation acceptance; missing OS/engine is explicitly skipped."""
import json
import os
import shutil
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.execution import child_env, run_action
from coder_agent_adhoc.windows_sandbox import launch, SandboxUnavailable

GODOT = os.getenv('GODOT_BINARY') or shutil.which('godot') or shutil.which('godot4')


@unittest.skipUnless(os.name == 'nt' and GODOT, 'Windows AppContainer + real Godot required')
class NativeSandbox(unittest.TestCase):
    def test_files_network_job_and_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage = root / 'sandbox'
            game = stage / 'game'
            game.mkdir(parents=True)
            host = root / 'private.txt'
            host.write_text('dummy canary')
            blocked = root / 'blocked.txt'
            spawned = game / 'spawned.txt'
            (game / 'project.godot').write_text('[application]\nconfig/name="Security test"\n')
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.settimeout(.2)
            port = listener.getsockname()[1]
            hits, stop = [], threading.Event()
            def serve():
                while not stop.is_set():
                    try:
                        conn, _ = listener.accept()
                        hits.append(True)
                        conn.close()
                    except socket.timeout:
                        pass
                    except OSError:
                        break
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            code = """extends SceneTree
func _initialize():
    print("READ:", FileAccess.open(%s, FileAccess.READ) != null)
    print("WRITE:", FileAccess.open(%s, FileAccess.WRITE) != null)
    print("ALLOWED:", FileAccess.open("res://allowed.txt", FileAccess.WRITE) != null)
    print("KEY:", not OS.get_environment("CODER_OPENROUTER_API_KEY").is_empty())
    var pid = OS.create_process(%s, ["/c", "echo spawned > " + %s])
    print("SPAWN:", pid)
    var tcp = StreamPeerTCP.new()
    print("CONNECT:", tcp.connect_to_host("127.0.0.1", %d))
    for i in range(20):
        tcp.poll()
        await process_frame
    print("TCP:", tcp.get_status())
    quit()
""" % (json.dumps(host.as_posix()), json.dumps(blocked.as_posix()),
       json.dumps((Path(os.environ['SYSTEMROOT']) / 'System32/cmd.exe').as_posix()),
       json.dumps(spawned.as_posix()), port)
            (game / 'check.gd').write_text(code, encoding='utf-8')
            try:
                result = launch(GODOT, ['--headless', '--path', str(game), '--script', 'res://check.gd'], stage, child_env())
            finally:
                stop.set()
                listener.close()
                thread.join(1)
            self.assertEqual(result['returncode'], 0, result)
            for expected in ('READ:false', 'WRITE:false', 'ALLOWED:true', 'KEY:false', 'SPAWN:-1'):
                self.assertIn(expected, result['output'])
            self.assertFalse(hits)
            self.assertFalse(blocked.exists())
            self.assertFalse(spawned.exists())
            self.assertTrue(result['sandbox']['token_is_appcontainer'])
            self.assertEqual(result['sandbox']['network_capabilities'], [])

    def test_real_scene_and_no_original_uid_changes(self):
        fixture = Path(__file__).parent / 'fixtures/godot'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(fixture / 'game', root / 'game')
            def snapshot():
                return {f.relative_to(root).as_posix(): f.read_bytes() for f in (root / 'game').rglob('*') if f.is_file()}
            before = snapshot()
            plan = json.loads((fixture / 'coder_plan.json').read_text(encoding='utf-8'))
            with patch.object(C, 'ROOT', root), patch.object(C, 'GAME_DIR', root / 'game'):
                for action in ('syntax', 'boot'):
                    result = run_action(plan, action)
                    self.assertEqual(result['returncode'], 0, result)
                    self.assertIsNone(result['reason'])
                    self.assertIn('sandbox', result)
                    self.assertNotIn('SCRIPT ERROR:', result['error_check_output'])
            self.assertEqual(before, snapshot())

    def test_native_timeout_and_output_limit(self):
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td)
            (stage / 'project.godot').write_text('[application]\nconfig/name="bounded"\n')
            (stage / 'wait.gd').write_text('extends SceneTree\nfunc _initialize():\n    pass\n')
            result = launch(GODOT, ['--headless', '--path', str(stage), '--script', 'res://wait.gd'], stage, child_env(), timeout=1)
            self.assertEqual(result['reason'], 'timeout')
            (stage / 'flood.gd').write_text('extends SceneTree\nfunc _initialize():\n    for i in range(10000): print("x".repeat(100))\n    quit()\n')
            result = launch(GODOT, ['--headless', '--path', str(stage), '--script', 'res://flood.gd'], stage, child_env(), output_limit=4096)
            self.assertEqual(result['reason'], 'output_limit')
            self.assertLessEqual(len(result['output'].encode()), 4096)


class FailClosed(unittest.TestCase):
    def test_no_native_fallback_when_sandbox_fails(self):
        with patch('coder_agent_adhoc.godot_runtime.run_godot', side_effect=SandboxUnavailable('test denial')):
            with self.assertRaisesRegex(FileNotFoundError, 'runtime_unavailable: sandbox'):
                run_action({'profile': {'renderer': 'godot'}}, 'boot')

    @unittest.skipUnless(os.name == 'nt', 'Windows AppContainer required')
    def test_large_stdin_cannot_bypass_timeout(self):
        import sys
        with tempfile.TemporaryDirectory() as td:
            result = launch(sys.executable, ['-I', '-c', 'import time;time.sleep(10)'], Path(td), child_env(),
                            timeout=1, read_dirs=(sys.prefix,), stdin='x' * 100000)
        self.assertEqual(result['reason'], 'timeout')
