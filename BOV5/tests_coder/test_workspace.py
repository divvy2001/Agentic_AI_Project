"""Initial Build backups, preserved upstream files, and unchanged-file smoke reuse."""
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from langchain_core.messages import AIMessage

import test_harness as H
from test_harness import Fake, call, calls, manual, write, INIT
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc import agent_coder as A
from coder_agent_adhoc.workspace import prepare_initial_workspace, snapshot
from coder_agent_adhoc.diagnostics import command_summary
from coder_agent_adhoc.adapters.godot import source_check


class WorkspaceTests(unittest.TestCase):
    setUp = H.Harness.setUp
    tearDown = H.Harness.tearDown
    stage = H.Harness.stage
    run_fake = H.Harness.run_fake

    def test_assets_only_continues_without_backup(self):
        C.GAME_DIR.mkdir()
        (C.GAME_DIR / 'assets').mkdir()
        asset = C.GAME_DIR / 'assets/sprite.bin'
        asset.write_bytes(b'asset-original')
        result = prepare_initial_workspace(allowed_assets={'game/assets/sprite.bin'})
        self.assertIsNone(result['backup_path'])
        self.assertEqual(result['action'], 'upstream_directories_only')
        self.assertEqual(asset.read_bytes(), b'asset-original')

    def test_assets_and_tests_preserved(self):
        for name in ('assets', 'tests'):
            (C.GAME_DIR / name).mkdir(parents=True)
            (C.GAME_DIR / name / 'input.txt').write_text(name)
        result = prepare_initial_workspace(allowed_assets={'game/assets/input.txt'})
        self.assertIsNone(result['backup_path'])
        self.assertEqual(set(result['preserved_directories']), {'assets', 'tests'})

    def test_previous_game_fully_backed_up_and_new_tree_clean(self):
        self.stage()
        (C.GAME_DIR / 'assets').mkdir()
        (C.GAME_DIR / 'assets/preserved.bin').write_bytes(b'original asset')
        (C.GAME_DIR / 'tests').mkdir()
        (C.GAME_DIR / 'tests/frozen.py').write_text('# frozen test')
        (C.GAME_DIR / 'assets/old_task.png').write_bytes(b'previous task art')
        old = snapshot(C.GAME_DIR)
        result = prepare_initial_workspace(allowed_assets={'game/assets/preserved.bin'})
        # Assets the current Plan does not authorize go only to the backup.
        self.assertFalse((C.GAME_DIR / 'assets/old_task.png').exists())
        self.assertEqual(result['stale_files_backed_up'], ['assets/old_task.png'])
        backup = C.ROOT / result['backup_path']
        self.assertEqual(snapshot(backup), old)
        self.assertFalse((C.GAME_DIR / 'main.py').exists())
        self.assertEqual((C.GAME_DIR / 'assets/preserved.bin').read_bytes(), b'original asset')
        self.assertEqual((C.GAME_DIR / 'tests/frozen.py').read_text(), '# frozen test')

    def test_repeat_build_uses_distinct_backups(self):
        self.stage()
        one = prepare_initial_workspace()
        (C.GAME_DIR / 'main.py').write_text('second generation')
        two = prepare_initial_workspace()
        self.assertNotEqual(one['backup_path'], two['backup_path'])
        self.assertIn('second generation', (C.ROOT / two['backup_path'] / 'main.py').read_text())

    def test_dry_run_never_moves_existing_game(self):
        self.stage()
        before = snapshot(C.GAME_DIR)
        result = prepare_initial_workspace(dry_run=True)
        self.assertEqual(result['action'], 'would_backup_and_reset')
        self.assertEqual(snapshot(C.GAME_DIR), before)
        self.assertFalse((C.ROOT / 'backups').exists())

    def test_asset_copy_failure_leaves_original_intact(self):
        self.stage()
        (C.GAME_DIR / 'assets').mkdir()
        (C.GAME_DIR / 'assets/a.txt').write_text('keep')
        before = snapshot(C.GAME_DIR)
        with patch('coder_agent_adhoc.workspace.shutil.copy2', side_effect=OSError('simulated disk error')):
            with self.assertRaises(OSError):
                prepare_initial_workspace(allowed_assets={'game/assets/a.txt'})
        self.assertEqual(snapshot(C.GAME_DIR), before)
        self.assertFalse((C.ROOT / 'backups').exists())

    def test_swap_failure_rolls_back_without_losing_old_game(self):
        self.stage()
        before = snapshot(C.GAME_DIR)
        original_rename = Path.rename
        def rename(source, destination):
            if source.name.startswith('.coder-game-'):
                raise OSError('simulated swap failure')
            return original_rename(source, destination)
        with patch.object(Path, 'rename', autospec=True, side_effect=rename):
            with self.assertRaises(OSError):
                prepare_initial_workspace()
        self.assertEqual(snapshot(C.GAME_DIR), before)

    def test_missing_key_and_invalid_plan_never_move_old_game(self):
        self.stage()
        before = snapshot(C.GAME_DIR)
        with patch.object(C, 'CODER_OPENROUTER_API_KEY', ''):
            result = A.run_coder()
        self.assertEqual(result['reason'], 'coder_key_missing')
        self.assertEqual(snapshot(C.GAME_DIR), before)
        C.PLAN_FILE.write_text('{}')
        result = A.run_coder()
        self.assertIn('invalid_plan', result['reason'])
        self.assertEqual(snapshot(C.GAME_DIR), before)

    def test_repair_never_prepares_or_backs_up_game(self):
        feedback = self.stage()
        with patch.object(A, 'prepare_initial_workspace') as prepare:
            result, _ = self.run_fake([manual(), AIMessage(content='coverage')], 'repair', feedback)
        prepare.assert_not_called()
        self.assertFalse((C.ROOT / 'backups').exists())

    def test_invalid_feedback_cannot_trigger_backup(self):
        self.stage()
        before = snapshot(C.GAME_DIR)
        with patch.object(A, 'create_model') as model:
            result = A.run_coder(mode='repair', feedback_path='../invalid.json')
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(snapshot(C.GAME_DIR), before)
        self.assertFalse((C.ROOT / 'backups').exists())
        model.assert_not_called()

    def test_actual_build_backs_up_old_code_then_generates_and_reuses_smoke(self):
        self.stage()
        source = (C.GAME_DIR / 'main.py').read_text(encoding='utf-8')
        fake = Fake([calls(INIT, write('game/main.py', source)),
                     manual(), AIMessage(content='never requested')])
        from coder_agent_adhoc.gates import smoke as real_smoke
        with patch.object(A, 'create_model', return_value=fake), patch.object(A, 'smoke', wraps=real_smoke) as checks:
            result = A.run_coder()
        self.assertEqual(result['status'], 'ready_for_testing', result)
        self.assertTrue(result['workspace_preparation']['backup_path'])
        self.assertEqual(checks.call_count, 1)
        # Passing gates end the call at once; no extra paid round for coverage claims.
        self.assertEqual(result['usage']['calls'], 2)
        self.assertEqual(result['coverage_status'], 'not_provided')

    def test_old_manual_cannot_satisfy_new_build(self):
        self.stage()
        source = (C.GAME_DIR / 'main.py').read_text(encoding='utf-8')
        C.PLAY_MANUAL_FILE.write_text(json.dumps(dict(test_input='', expected_win_output='', expected_lose_output='', notes='OLD')))
        result, _ = self.run_fake([calls(INIT, write('game/main.py', source)), AIMessage(content='done')])
        self.assertNotEqual(result['status'], 'ready_for_testing')
        events = C.TRACE_FILE.read_text(encoding='utf-8')
        self.assertIn('fresh_play_manual_required', events)

    def test_changed_code_invalidates_passed_smoke(self):
        self.stage()
        source = (C.GAME_DIR / 'main.py').read_text(encoding='utf-8')
        # Broken first build fails syntax; the fix is re-checked, never reused from before.
        fake = Fake([calls(INIT, write('game/main.py', 'def broken(:')), manual(),
                     call('write_file', dict(path='game/main.py', content=source)),
                     AIMessage(content='done')])
        from coder_agent_adhoc.gates import smoke as real_smoke
        with patch.object(A, 'create_model', return_value=fake), patch.object(A, 'smoke', wraps=real_smoke) as checks:
            result = A.run_coder()
        self.assertEqual(result['status'], 'ready_for_testing', result)
        self.assertEqual(checks.call_count, 2)
        self.assertEqual(result['debug_statistics']['local_failure_events'], 1)
        self.assertEqual(result['debug_statistics']['self_debug_attempts'], 1)
        self.assertEqual(result['debug_statistics']['external_repair_invocations'], 0)

    def test_scene_format_precheck_has_actionable_error(self):
        self.stage('godot')
        plan = json.loads(C.PLAN_FILE.read_text(encoding='utf-8'))
        (C.GAME_DIR / 'main.tscn').write_text('<gd_scene><node /></gd_scene>')
        self.assertIn('not XML', source_check(plan)[1])
        (C.GAME_DIR / 'main.tscn').write_text('[gd_scene format=3]\n[node name="Main" type="Node3D"]\n[sub_resource type="BoxMesh" id="1"]')
        self.assertIn('BEFORE', source_check(plan)[1])

    def test_compact_errors_retain_godot_source_context(self):
        self.stage('godot')
        result = command_summary(dict(returncode=0, reason=None, output='progress\nSCRIPT ERROR: Parse Error: bad\n at: res://main.gd:6\nmore progress\n'))
        self.assertIn('game/main.gd:6', result['source_context'])
        self.assertTrue(any('SCRIPT ERROR' in line for line in result['diagnostics']))
