"""Visible handoff contracts; no API calls or desktop interaction."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from coder_agent_adhoc import initial_build, repair, launch_game as L
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.play_host import import_error_text


class VisibleLaunch(unittest.TestCase):
    def test_only_known_volume_query_pair_is_excluded_not_real_errors(self):
        pair = 'ERROR: Method/function failed. Returning: ""\r\n   at: get_filesystem_type (drivers/windows/dir_access_windows.cpp:412)\r\n'
        self.assertEqual(import_error_text(pair + 'import complete'), 'import complete')
        for real in ('ERROR: Texture failed\n', 'SCRIPT ERROR: Parse Error\n', pair.replace('get_filesystem_type', 'other_function')):
            self.assertEqual(import_error_text(pair + real), real)

    def test_failure_and_dry_run_never_open(self):
        with patch.object(L, 'launch_game') as launch:
            for status in ('blocked', 'budget_exhausted', 'dry_run'):
                r = L.finish_with_play({'status': status})
                self.assertEqual(r['play_session']['status'], 'not_run')
            launch.assert_not_called()

    def test_public_build_defaults_to_visible_handoff_and_can_disable(self):
        ready = dict(status='ready_for_testing', renderer='terminal', entry_point='game/main.py')
        with patch('coder_agent_adhoc.agent_coder.run_coder', side_effect=lambda **kw: dict(ready)):
            with patch.object(L, 'launch_game', return_value=dict(status='started', pid=123)) as launch:
                result = initial_build.run_initial_build()
                self.assertEqual(result['play_session']['status'], 'started')
                launch.assert_called_once_with('terminal', 'game/main.py')
                launch.reset_mock()
                result = initial_build.run_initial_build(launch_game=False)
                self.assertEqual(result['play_session']['reason'], 'disabled_by_caller')
                launch.assert_not_called()

    def test_launch_failure_is_not_gameplay_pass_or_generation_failure(self):
        with patch.object(L, 'launch_game', side_effect=OSError('missing runtime')):
            r = L.finish_with_play(dict(status='ready_for_testing', renderer='godot', entry_point='game/main.tscn'))
        self.assertEqual(r['status'], 'ready_for_testing')
        self.assertEqual(r['play_session']['status'], 'failed')

    def test_repair_success_opens_but_wrong_stage_does_not(self):
        ready = dict(status='ready_for_testing', renderer='pygame', entry_point='game/main.py')
        with patch.object(repair, 'validate_feedback', return_value=dict(status='fail', failing_stage='logic_coder')), \
             patch('coder_agent_adhoc.agent_coder.run_coder', return_value=ready), \
             patch.object(L, 'launch_game', return_value=dict(status='started', pid=456)) as launch:
            result = repair.run_repair('feedback.json')
            self.assertEqual(result['play_session']['status'], 'started')
            launch.assert_called_once_with('pygame', 'game/main.py')
        with patch.object(repair, 'validate_feedback', return_value=dict(status='fail', failing_stage='asset')), \
             patch.object(L, 'launch_game') as launch:
            self.assertEqual(repair.run_repair('feedback.json')['status'], 'blocked')
            launch.assert_not_called()

    def test_commands_environment_and_staging_for_each_renderer(self):
        for renderer in ('terminal', 'pygame', 'godot'):
            with self.subTest(renderer=renderer), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                game = root / 'game'
                game.mkdir()
                entry = 'game/main.tscn' if renderer == 'godot' else 'game/main.py'
                (root / entry).write_text('source', encoding='utf-8')
                captured = {}
                class Host:
                    def poll(self): return None
                def popen(argv, **kwargs):
                    session = Path(argv[-1])
                    captured.update(request=json.loads((session / 'request.json').read_text()), argv=argv, kwargs=kwargs)
                    (session / 'launch.json').write_text(json.dumps(dict(status='started', pid=456)))
                    return Host()
                with patch.object(C, 'ROOT', root), patch.object(C, 'GAME_DIR', game), \
                     patch.object(L.subprocess, 'Popen', side_effect=popen), \
                     patch('coder_agent_adhoc.godot_runtime.binary', return_value='trusted-godot.exe'), \
                     patch.dict(os.environ, {'CODER_OPENROUTER_API_KEY': 'secret-never-copy', 'SDL_VIDEODRIVER': 'dummy'}):
                    r = L.launch_game(renderer, entry)
                self.assertEqual(r['status'], 'started')
                req = captured['request']
                self.assertNotIn('secret-never-copy', json.dumps(req))
                self.assertNotIn('SDL_VIDEODRIVER', req['env'])
                self.assertEqual(req['timeout'], 7200)
                self.assertNotIn('--headless', req['args'])
                self.assertNotIn('--quit-after', req['args'])
                stage = root / r['session_dir'] / 'runtime'
                self.assertEqual((stage / entry).read_text(), 'source')
                if renderer != 'godot':
                    self.assertEqual(req['args'][-1], entry)
                    self.assertTrue((stage / 'play_child.py').is_file())
                self.assertEqual(captured['kwargs']['creationflags'], L.subprocess.CREATE_NO_WINDOW)

    def test_secret_in_game_rejected_before_spawn(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'game').mkdir()
            (root / 'game/main.py').write_text('print(1)')
            (root / 'game/.env').write_text('private')
            with patch.object(C, 'ROOT', root), patch.object(C, 'GAME_DIR', root / 'game'), patch.object(L.subprocess, 'Popen') as spawn:
                with self.assertRaisesRegex(ValueError, 'secret_file'):
                    L.launch_game('terminal', 'game/main.py')
                spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
