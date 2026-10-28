"""Regression tests for the review counterexamples; real runtimes, no model API calls."""
import json, os, shutil, unittest
from pathlib import Path
from unittest.mock import patch
from langchain_core.messages import AIMessage
import test_harness as H
from test_harness import call, manual, Fake
from coder_agent_adhoc import agent_coder as A, contracts
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.execution import run_action
from coder_agent_adhoc.gates import smoke
from coder_agent_adhoc.run_context import CURRENT, RunContext, workspace_lock
from coder_agent_adhoc.tools import tools_coder as T


class Hardening(unittest.TestCase):
    setUp=H.Harness.setUp
    tearDown=H.Harness.tearDown
    stage=H.Harness.stage
    run_fake=H.Harness.run_fake

    def make_manual(self):
        C.PLAY_MANUAL_FILE.write_text(json.dumps(dict(test_input='',expected_win_output='',expected_lose_output='',notes='startup only')))

    def test_null_and_list_manifests_block_before_model_and_mutation(self):
        self.stage();p=json.loads(C.PLAN_FILE.read_text(encoding='utf-8'));p['architecture']['assets']['strategy']='ai_art'
        C.PLAN_FILE.write_text(json.dumps(p));before=(C.GAME_DIR/'main.py').read_bytes()
        for value in (None,[],{'task_id':p['game_title'],'framework':'terminal','assets':None}):
            C.ASSET_MANIFEST_FILE.write_text(json.dumps(value))
            with patch.object(A,'create_model') as model:
                result=A.run_coder();model.assert_not_called()
            self.assertEqual(result['status'],'blocked');self.assertIn('asset_missing',result['reason'])
            self.assertEqual((C.GAME_DIR/'main.py').read_bytes(),before)
            self.assertFalse((C.ROOT/'backups').exists())

    def test_nested_plan_shapes_are_structured_errors(self):
        self.stage();original=json.loads(C.PLAN_FILE.read_text(encoding='utf-8'))
        values=[None,[],dict(original,architecture=None),dict(original,requirements=[None])]
        bad=json.loads(json.dumps(original));bad['architecture']['assets']['sprites']=[None];values.append(bad)
        for value in values:
            C.PLAN_FILE.write_text(json.dumps(value))
            with patch.object(A,'create_model') as model:
                result=A.run_coder(dry_run=True);model.assert_not_called()
            self.assertEqual(result['status'],'blocked')

    def test_optional_failed_or_corrupt_assets_not_exposed(self):
        self.stage();p=contracts.plan();p['architecture']['assets']['strategy']='procedural'
        (C.GAME_DIR/'bad.png').write_bytes(b'invalid image')
        entries=[dict(id='bad',path='game/bad.png',generation_status='generated',validation_status='passed',required=False),
                 dict(id='failed',path='game/main.py',generation_status='failed',validation_status='failed',required=False)]
        C.ASSET_MANIFEST_FILE.write_text(json.dumps(dict(task_id=p['game_title'],framework='terminal',assets=entries)))
        self.assertEqual(contracts.assets(p),[])

    def test_python_host_read_and_plan_delete_denied(self):
        self.stage();host=self.root/'private_dummy.txt';host.write_text('review dummy')
        plan_before=C.PLAN_FILE.read_bytes()
        cases=[f'from pathlib import Path\nprint(Path({str(host)!r}).read_text())\n',
               f'import os\nos.remove({str(C.PLAN_FILE)!r})\n',
               "import socket\nsocket.create_connection(('127.0.0.1',9))\n"]
        for source in cases:
            (C.GAME_DIR/'main.py').write_text(source)
            result=run_action(contracts.plan(),'boot')
            self.assertNotEqual(result['returncode'],0,result)
            self.assertIn('PermissionError',result['output'])
            self.assertTrue(result['sandbox']['token_is_appcontainer'])
        self.assertEqual(host.read_text(),'review dummy');self.assertEqual(C.PLAN_FILE.read_bytes(),plan_before)

    def test_parallel_python_launches_keep_runtime_permissions(self):
        from concurrent.futures import ThreadPoolExecutor
        self.stage();p=contracts.plan()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:run_action(p,'syntax'),range(2)))
        for result in results:
            self.assertEqual(result['returncode'],0,result)
            self.assertIsNone(result['reason'])
            self.assertIn('CODER_SYNTAX_OK',result['output'])

    def test_runtime_initialization_failure_is_not_sent_as_game_repair(self):
        self.stage();self.make_manual()
        with patch('coder_agent_adhoc.gates.run_action',return_value=dict(returncode=125,reason='runtime_unavailable: python_initialization',output='Fatal Python error:')):
            gates,_,reason=smoke(contracts.plan(),{},set(),'repair')
        self.assertIn('runtime_unavailable',reason);self.assertEqual(gates['syntax_or_import'],'failed')

    def test_runtime_asset_mutation_blocked_and_original_unchanged(self):
        self.stage();asset=C.GAME_DIR/'assets/review.bin';asset.parent.mkdir();asset.write_bytes(b'original')
        (C.GAME_DIR/'main.py').write_text("from pathlib import Path\nPath('game/assets/review.bin').write_bytes(b'changed')\nprint('done')\n")
        self.make_manual();gates,_,reason=smoke(contracts.plan(),{'game/assets/review.bin':b'original'},set(),'repair')
        self.assertIsNotNone(reason);self.assertEqual(gates['boot'],'failed');self.assertEqual(asset.read_bytes(),b'original')

    def test_post_runtime_protected_check_catches_adapter_side_effect(self):
        self.stage();asset=C.GAME_DIR/'assets/review.bin';asset.parent.mkdir();asset.write_bytes(b'original');self.make_manual()
        def action(p,which):
            if which=='boot':asset.write_bytes(b'changed')
            return dict(returncode=0,reason=None,output='CODER_OBSERVED:{"game_lines":3,"inputs":1}')
        with patch('coder_agent_adhoc.gates.run_action',side_effect=action):
            gates,_,reason=smoke(contracts.plan(),{'game/assets/review.bin':b'original'},set(),'repair')
        self.assertEqual(gates['boot'],'failed');self.assertIn('protected_input_changed',reason)

    def test_terminal_static_stub_rejected(self):
        self.stage();self.make_manual();(C.GAME_DIR/'main.py').write_text("a=1\nb=2\nprint('stub')\n")
        gates,_,reason=smoke(contracts.plan(),{},set(),'repair')
        self.assertEqual(gates['boot'],'failed');self.assertEqual(reason,'update_path_not_observed')

    def test_terminal_wait_without_sample_is_valid(self):
        self.stage();self.make_manual();p=contracts.plan();p['architecture'].pop('test_input_example',None)
        (C.GAME_DIR/'main.py').write_text("print('Ready')\na=1\ncommand=input('Action: ')\nprint(command)\n")
        gates,evidence,reason=smoke(p,{},set(),'repair')
        self.assertIsNone(reason,evidence);self.assertEqual(gates['boot'],'passed')
        self.assertIn('"waiting_for_input": true',evidence[-1]['output'])

    def test_prose_is_not_used_as_stdin(self):
        self.stage();p=contracts.plan();p['architecture']['test_input_example']='Press W then enter\nRepeat until win\n'
        with patch('coder_agent_adhoc.python_runtime.run_python',return_value={}) as run:
            run_action(p,'boot')
        self.assertEqual(run.call_args.args[2:4],('',False))

    def test_pygame_straight_line_presentations_are_not_an_update_loop(self):
        self.stage('pygame');self.make_manual()
        source='import pygame\npygame.init()\npygame.display.set_mode((64,64))\n'+'pygame.display.flip()\n'*8
        (C.GAME_DIR/'main.py').write_text(source)
        gates,_,reason=smoke(contracts.plan(),{},set(),'repair')
        self.assertEqual(gates['boot'],'failed');self.assertEqual(reason,'update_path_not_observed')

    def test_repair_rejects_unread_replacement_and_no_change_finish(self):
        fb=self.stage();before=(C.GAME_DIR/'main.py').read_bytes()
        result,fake=self.run_fake([call('write_file',dict(path='game/main.py',content="a=1\nb=2\nprint('unrelated')\n",reason='rewrite')),manual()],'repair',fb)
        self.assertNotEqual(result['status'],'ready_for_testing');self.assertEqual((C.GAME_DIR/'main.py').read_bytes(),before)
        self.assertTrue(any('repair_read_current_source_required' in str(m.content) for msgs in fake.inputs for m in msgs if m.type=='tool'))

    def test_repair_stale_read_and_unexplained_rewrite_rejected(self):
        self.stage();ctx=RunContext('repair',contracts.plan());token=CURRENT.set(ctx)
        try:
            T.read_file.invoke(dict(paths=['game/main.py']))
            with self.assertRaisesRegex(ValueError,'rewrite_reason_required'):
                T.write_file.invoke(dict(path='game/main.py',content='new'))
            f=C.GAME_DIR/'main.py';f.write_text(f.read_text()+'\n# concurrent change\n')
            with self.assertRaisesRegex(ValueError,'read_current_source_required'):
                T.apply_patch.invoke(dict(path='game/main.py',old='score > 3',new='score >= 3'))
        finally:CURRENT.reset(token)

    def test_failed_repair_restores_original_code_and_records_diff(self):
        fb=self.stage();before=(C.GAME_DIR/'main.py').read_bytes()
        class TransportFailure(Fake):
            def invoke(self,messages):
                if len(self.inputs)==2:raise RuntimeError('offline simulated transport failure')
                return super().invoke(messages)
        fake=TransportFailure([call('read_file',dict(paths=['game/main.py'])),call('apply_patch',dict(path='game/main.py',old='score > 3',new='score >= 3'))])
        with patch.object(A,'create_model',return_value=fake):result=A.run_coder(mode='repair',feedback_path=fb)
        self.assertEqual(result['status'],'blocked');self.assertEqual((C.GAME_DIR/'main.py').read_bytes(),before)
        self.assertIn('game/main.py',result['rollback']['restored_files']);self.assertIn('score >= 3',result['changes'][0]['diff'])
        events=[json.loads(line) for line in C.TRACE_FILE.read_text(encoding='utf-8').splitlines()]
        self.assertTrue(all(e['attempt_id']==result['attempt_id'] for e in events))

    def test_preflight_failure_leaves_old_game_in_place(self):
        self.stage();before=(C.GAME_DIR/'main.py').read_bytes()
        with patch.object(A,'create_model',side_effect=RuntimeError('construction failed')):result=A.run_coder()
        self.assertEqual(result['status'],'blocked');self.assertEqual((C.GAME_DIR/'main.py').read_bytes(),before)
        self.assertFalse((C.ROOT/'backups').exists())

    def test_context_state_is_not_shared(self):
        self.stage();first=RunContext('repair',contracts.plan());second=RunContext('repair',contracts.plan())
        token=CURRENT.set(first)
        try:
            T.read_file.invoke(dict(paths=['game/main.py']));self.assertIn('game/main.py',first.read_versions)
            nested=CURRENT.set(second)
            try:self.assertEqual(second.read_versions,{})
            finally:CURRENT.reset(nested)
            self.assertIs(CURRENT.get(),first)
        finally:CURRENT.reset(token)

    def test_workspace_lock_prevents_second_writer(self):
        with workspace_lock():
            with self.assertRaisesRegex(ValueError,'workspace_busy'):
                with workspace_lock():pass
        with workspace_lock():pass

    def test_pending_swap_requires_recovery(self):
        self.stage();(C.ROOT/'traces/workspace_swap.json').write_text('{"state":"prepared"}')
        before=(C.GAME_DIR/'main.py').read_bytes()
        from coder_agent_adhoc.workspace import prepare_initial_workspace
        with self.assertRaisesRegex(ValueError,'workspace_recovery_required'):prepare_initial_workspace()
        self.assertEqual((C.GAME_DIR/'main.py').read_bytes(),before)

    def test_token_budget_stops_before_tools_and_preserves_unknown_cost(self):
        self.stage();response=AIMessage(content='',tool_calls=[dict(name='read_plan',args={},id='budget')],
                                       usage_metadata=dict(input_tokens=100,output_tokens=1,total_tokens=101))
        with patch.object(C,'CODER_MAX_TOKENS',100):result,_=self.run_fake([response])
        self.assertEqual(result['reason'],'token_budget_exhausted');self.assertIsNone(result['usage']['reported_cost_usd'])

    def test_optional_cost_cap_stops_when_provider_cost_is_unknown(self):
        self.stage()
        with patch.object(C,'CODER_MAX_COST_USD',1):result,_=self.run_fake([call('read_plan',{})])
        self.assertEqual(result['reason'],'cost_metadata_unavailable');self.assertIsNone(result['usage']['reported_cost_usd'])

    def test_godot_dictionary_input_events_rejected_before_engine(self):
        self.stage('godot');self.make_manual()
        f=C.GAME_DIR/'project.godot'
        f.write_text('[application]\nrun/main_scene="res://main.tscn"\n[input]\nmove={"events": [{"type":"InputEventKey","physical_keycode":87}]}\n')
        with patch('coder_agent_adhoc.gates.run_action') as action:
            gates,evidence,reason=smoke(contracts.plan(),{},set(),'repair');action.assert_not_called()
        self.assertEqual(reason,'invalid_godot_input_events');self.assertIn('InputEventKey.new()',evidence[0]['output'])

    @unittest.skipUnless(os.name=='nt' and os.getenv('GODOT_BINARY'),'real Godot required')
    def test_godot_ready_quit_is_rejected(self):
        self.stage('godot');self.make_manual()
        (C.GAME_DIR/'main.gd').write_text('extends Node2D\nfunc _ready():\n    get_tree().quit()\n')
        gates,_,reason=smoke(contracts.plan(),{},set(),'repair')
        self.assertEqual(gates['boot'],'failed');self.assertEqual(reason,'godot_update_path_not_observed')

    @unittest.skipUnless(os.name=='nt' and os.getenv('GODOT_BINARY'),'real Godot required')
    def test_godot_multiple_scripts_and_scene_references_update(self):
        self.stage('godot');self.make_manual();p=contracts.plan()
        (C.GAME_DIR/'helper.gd').write_text('extends Node2D\nvar ticks: int = 0\nfunc _process(_delta):\n    ticks += 1\n')
        (C.GAME_DIR/'child.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://helper.gd" id="1"]\n[node name="Child" type="Node2D"]\nscript = ExtResource("1")\n')
        (C.GAME_DIR/'main.gd').write_text('extends Node2D\nconst CHILD = preload("res://child.tscn")\nfunc _ready():\n    add_child(CHILD.instantiate())\n')
        p['architecture']['files'] += [dict(path='game/helper.gd',purpose='child update'),dict(path='game/child.tscn',purpose='child scene')]
        gates,evidence,reason=smoke(p,{},set(),'repair')
        self.assertIsNone(reason,evidence);self.assertEqual(gates['boot'],'passed');self.assertEqual(evidence[-1]['observed']['update_frames'],3)

if __name__=='__main__':unittest.main()
