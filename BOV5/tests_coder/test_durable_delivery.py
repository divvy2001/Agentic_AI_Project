"""Counterexamples for durable generation, provider isolation and empty delivery.

These are infrastructure/renderer tests, not generated-game success-rate results.
"""
import json
import unittest
from unittest.mock import patch
from langchain_core.messages import AIMessage
import test_harness as H
from coder_agent_adhoc import agent_coder as A, build_state, contracts, presentation
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.adapters import godot
from coder_agent_adhoc.launch_game import validate_existing_game


def billed(message, error=False):
    return message.model_copy(update=dict(usage_metadata=dict(input_tokens=1, output_tokens=1, total_tokens=2),
        response_metadata=dict(token_usage=dict(cost=0), **({'finish_reason': 'error'} if error else {}))))


def failed():
    return billed(AIMessage(content=''), error=True)


class DurableDelivery(unittest.TestCase):
    setUp = H.Harness.setUp
    tearDown = H.Harness.tearDown
    stage = H.Harness.stage

    def writes(self):
        source = (H.FIX / 'terminal/game/main.py').read_text(encoding='utf-8')
        return billed(H.calls(H.INIT, H.write('game/main.py', source)))

    def run_fake(self, responses, **kwargs):
        fake = H.Fake(responses)
        with patch.object(A, 'create_model', return_value=fake):
            return A.run_coder(**kwargs), fake

    def test_two_separated_provider_errors_get_independent_bounded_retries(self):
        self.stage()
        with patch.object(C, 'CODER_MAX_STEPS', 8):
            result, fake = self.run_fake([failed(), self.writes(), failed(), billed(H.manual())])
        self.assertEqual(result['status'], 'ready_for_testing', result)
        self.assertEqual(result['provider_error_retries'], 2)
        self.assertEqual(result['usage']['calls'], 4)
        self.assertEqual(len(fake.inputs), 4)

    def test_resume_keeps_code_and_inherits_calls_without_new_backup(self):
        self.stage()
        first, _ = self.run_fake([self.writes(), failed(), failed()])
        self.assertEqual(first['status'], 'blocked')
        before = build_state.game_hashes()
        backups = list((C.ROOT / 'backups').glob('*'))
        result, _ = self.run_fake([billed(H.manual())], resume_attempt_id=first['attempt_id'])
        self.assertEqual(result['status'], 'ready_for_testing', result)
        self.assertEqual(build_state.game_hashes(), before)
        self.assertEqual(list((C.ROOT / 'backups').glob('*')), backups)
        self.assertEqual(result['usage']['calls'], first['usage']['calls'] + 1)
        self.assertEqual(result['steps'], first['steps'] + 1)
        self.assertEqual(result['workspace_preparation']['action'], 'resumed_existing_build_no_reset')

    def test_resume_rejects_changed_source_before_any_model_invocation(self):
        self.stage()
        first, _ = self.run_fake([self.writes(), failed(), failed()])
        (C.GAME_DIR / 'main.py').write_text('changed externally')
        result, fake = self.run_fake([], resume_attempt_id=first['attempt_id'])
        self.assertIn('resume_source_changed', result['reason'])
        self.assertFalse(fake.inputs)

    def test_unknown_inflight_billing_prevents_resume_replay(self):
        self.stage()
        class Broken:
            def invoke(self, messages):
                raise ConnectionError('response body lost')
        with patch.object(A, 'create_model', return_value=Broken()):
            first = A.run_coder()
        result, fake = self.run_fake([], resume_attempt_id=first['attempt_id'])
        self.assertIn('resume_billing_audit_required', result['reason'])
        self.assertFalse(fake.inputs)

    def test_pending_tools_resume_once_without_repeating_paid_request(self):
        self.stage()
        original = A._run_tool
        def interrupt(ctx, step, call):
            if call.get('args', {}).get('path') == 'game/main.py':
                raise KeyboardInterrupt('controlled stop between tools')
            return original(ctx, step, call)
        source = (H.FIX / 'terminal/game/main.py').read_text(encoding='utf-8')
        response = billed(H.calls(H.INIT, H.write('game/main.py', source),
            ('write_play_manual', dict(test_input='1\\n1\\n1\\n', expected_win_output='WIN', expected_lose_output='', notes='score'))))
        with patch.object(A, '_run_tool', side_effect=interrupt), patch.object(A, 'create_model', return_value=H.Fake([response])):
            with self.assertRaises(KeyboardInterrupt):
                A.run_coder()
        state_file = next((C.ROOT / 'traces/build_state').glob('*.json'))
        state = json.loads(state_file.read_text(encoding='utf-8'))
        self.assertEqual(len(state['pending_calls']), 2)
        result, fake = self.run_fake([], resume_attempt_id=state['attempt_id'])
        self.assertEqual(result['status'], 'ready_for_testing', result)
        self.assertEqual(result['usage']['calls'], 1)
        self.assertFalse(fake.inputs)
        self.assertEqual(sum(c['path'] == 'game/__init__.py' for c in result['changes']), 1)

    def test_resume_does_not_reset_exhausted_token_budget(self):
        self.stage()
        with patch.object(C, 'CODER_MAX_TOKENS', 1):
            first, _ = self.run_fake([self.writes()])
            result, fake = self.run_fake([], resume_attempt_id=first['attempt_id'])
        self.assertEqual(result['reason'], 'token_budget_exhausted')
        self.assertFalse(fake.inputs)

    def test_failed_receipt_blocks_manual_launcher_without_engine(self):
        self.stage()
        first, _ = self.run_fake([failed(), failed()])
        with patch('coder_agent_adhoc.gates.smoke') as gate:
            with self.assertRaisesRegex(ValueError, 'last_build_not_ready'):
                validate_existing_game(contracts.plan())
            gate.assert_not_called()

    def test_logging_only_godot_scene_is_rejected(self):
        self.stage('godot')
        (C.GAME_DIR / 'main.gd').write_text('extends Node2D\nfunc _ready():\n    print("Game started!")\n')
        self.assertEqual(godot.source_check(contracts.plan())[0], 'godot_empty_game')

    def test_missing_godot_resource_reports_actual_reference(self):
        self.stage('godot')
        (C.GAME_DIR / 'main.gd').unlink()
        (C.GAME_DIR / 'main.tscn').write_text('[gd_scene format=3]\n[ext_resource type="Script" path="res://main.gd" id="1"]\n[node name="Main" type="Node2D"]\n')
        issue = godot.source_check(contracts.plan())
        self.assertEqual(issue[0], 'godot_missing_resource')
        self.assertIn('main.gd', issue[1])

    def test_visual_requirement_does_not_relabel_score_fixture_as_visual_pass(self):
        self.stage('godot')
        p = contracts.plan()
        self.assertFalse(presentation.expected(p))
        p['requirements'][0]['text'] += ' Display a visible board and HUD.'
        self.assertTrue(presentation.expected(p))

    def test_resumed_edits_require_a_read_and_reason_for_replacement(self):
        self.stage()
        from coder_agent_adhoc.run_context import RunContext, CURRENT
        from coder_agent_adhoc.tools import tools_coder as T
        ctx = RunContext('initial_build', contracts.plan())
        ctx.resuming = True
        token = CURRENT.set(ctx)
        before = (C.GAME_DIR / 'main.py').read_bytes()
        try:
            with self.assertRaisesRegex(ValueError, 'resume_read_current_source_required'):
                T.write_file.invoke(dict(path='game/main.py', content='print("replacement")'))
            T.read_file.invoke(dict(paths=['game/main.py']))
            with self.assertRaisesRegex(ValueError, 'resume_full_rewrite_reason_required'):
                T.write_file.invoke(dict(path='game/main.py', content='print("replacement")'))
            self.assertEqual((C.GAME_DIR / 'main.py').read_bytes(), before)
        finally:
            CURRENT.reset(token)

    def test_unplanned_scene_reference_rejected_before_overwriting_good_file(self):
        self.stage('godot')
        from coder_agent_adhoc.tools import tools_coder as T
        file = C.GAME_DIR / 'main.tscn'
        before = file.read_bytes()
        with self.assertRaisesRegex(ValueError, 'unplanned_godot_resource'):
            T.write_file.invoke(dict(path='game/main.tscn', content='[gd_scene format=3]\n[ext_resource type="PackedScene" path="res://invented.tscn" id="1"]\n[node name="Main" type="Node2D"]\n'))
        self.assertEqual(file.read_bytes(), before)

    def test_model_change_keeps_previous_usage_and_partitions_new_usage(self):
        usage = dict(model='old-model',calls=20,input_tokens=1000,output_tokens=200,
                     max_input_tokens_per_call=100,known_cost_usd=.4,cost_missing_calls=0)
        with patch.object(C, 'AGENT_MODEL', 'new-model'):
            A._record_usage(usage,billed(AIMessage(content='new response')))
        self.assertEqual(usage['calls'],21)
        self.assertEqual(usage['by_model']['old-model']['calls'],20)
        self.assertEqual(usage['by_model']['new-model']['calls'],1)
        self.assertEqual(usage['input_tokens'],1001)

    def test_real_sdk_transport_failure_does_not_blindly_retry(self):
        import httpx
        seen=[]
        def fail(request):
            seen.append(request)
            raise httpx.ReadError('response lost after possible billing',request=request)
        model=A.create_model()
        client=model.bound.root_client._client
        transport=httpx.MockTransport(fail)
        client._transport=transport
        # HTTPX may have environment-derived proxy mounts; use the same offline
        # transport for each mounted route, never contact a real endpoint.
        client._mounts={}
        from langchain_core.messages import HumanMessage
        with self.assertRaises(Exception):
            model.invoke([HumanMessage(content='offline billing safety test')])
        self.assertEqual(len(seen),1)
        client.close()

    def test_resume_idempotent_marker_write_is_not_a_rewrite_or_progress(self):
        self.stage()
        from coder_agent_adhoc.run_context import RunContext, CURRENT
        from coder_agent_adhoc.tools import tools_coder as T
        marker=C.GAME_DIR/'__init__.py'
        marker.write_text('')
        ctx=RunContext('initial_build',contracts.plan());ctx.resuming=True
        token=CURRENT.set(ctx)
        try:
            value=T.write_file.invoke(dict(path='game/__init__.py',content=''))
            self.assertIn('unchanged',value)
            self.assertFalse(ctx.changes)
        finally:CURRENT.reset(token)

    def test_recovery_context_overrides_fresh_build_and_retains_declarations(self):
        self.stage('godot')
        from coder_agent_adhoc.run_context import RunContext
        from coder_agent_adhoc.context import initial_messages,update_build_progress
        p=contracts.plan();ctx=RunContext('initial_build',p)
        state=dict(attempt_id='a'*32,written=[f['path'] for f in p['architecture']['files']],changes=[],
                   elapsed_seconds=2,game_sha256=build_state.game_hashes(),result=dict(steps=3,reason='provider error'),
                   usage=dict(model=C.AGENT_MODEL,calls=3,input_tokens=3,output_tokens=3,known_cost_usd=0,cost_missing_calls=0))
        messages,usage=build_state.restore(ctx,{},state,initial_messages('initial_build',p,[]))
        update_build_progress(messages,ctx)
        self.assertIn('RESUMPTION OVERRIDE',messages[0].content)
        data=json.loads(messages[1].content)
        self.assertEqual(data['files_to_write'],[])
        self.assertEqual(data['plan'],p)
        self.assertTrue(data['build_progress']['source_declarations'])

    def test_automatic_integration_does_not_wait_for_model_manual_or_run_shell(self):
        self.stage('godot')
        p=json.loads(C.PLAN_FILE.read_text(encoding='utf-8'))
        p['requirements'][0]['text']+=' Display a visible board.'
        C.PLAN_FILE.write_text(json.dumps(p),encoding='utf-8')
        writes=[H.write(f['path'],(C.ROOT/f['path']).read_text(encoding='utf-8')) for f in p['architecture']['files']]
        writes.append(H.write('game/project.godot','[application]\nrun/main_scene="res://main.tscn"\n'))
        gates=dict(plan_and_files='passed',syntax_or_import='failed',boot='not_run')
        with patch.object(A,'integration_smoke',return_value=(gates,[dict(returncode=1,output='SCRIPT ERROR: bad interface')],'syntax_failed')) as probe:
            result,fake=self.run_fake([billed(H.calls(*writes)),failed(),failed()])
        probe.assert_called_once()
        self.assertEqual(probe.call_args.kwargs,{'require_manual':False})
        self.assertIn('Harness integration phase',str(fake.inputs[1]))
        self.assertEqual(result['integration_check']['reason'],'syntax_failed')

    def test_resource_contract_ignores_displayed_path_text_and_allows_future_promised_scene(self):
        p=dict(architecture=dict(files=[dict(path='game/future.tscn')]))
        self.assertIsNone(godot.resource_contract_problem('extends Node2D\nfunc _ready():\n    print("res://not_a_resource.tscn")\n',p))
        self.assertIsNone(godot.resource_contract_problem('extends Node2D\nconst SCENE=preload("res://future.tscn")\n',p))
        self.assertEqual(godot.resource_contract_problem('const SCENE=preload("res://invented.tscn")',p)[0],'unplanned_godot_resource')

    def test_duplicate_scene_uid_rejected_without_overwriting_original(self):
        self.stage('godot')
        from coder_agent_adhoc.tools import tools_coder as T
        p=json.loads(C.PLAN_FILE.read_text(encoding='utf-8'));p['architecture']['files'].append(dict(path='game/other.tscn',purpose='other scene'))
        C.PLAN_FILE.write_text(json.dumps(p),encoding='utf-8')
        (C.GAME_DIR/'other.tscn').write_text('\n[gd_scene format=3 uid="uid://shared"]\n[node name="Other" type="Node2D"]\n')
        before=(C.GAME_DIR/'main.tscn').read_bytes()
        text='[gd_scene format=3 uid="uid://shared"]\n[node name="Main" type="Node2D"]\n'
        with self.assertRaisesRegex(ValueError,'godot_duplicate_scene_uid'):
            T.write_file.invoke(dict(path='game/main.tscn',content=text))
        self.assertEqual((C.GAME_DIR/'main.tscn').read_bytes(),before)
        self.assertIsNone(godot.scene_uid_problem(text.replace('shared','different'),'game/main.tscn',p))


    def test_native_delayed_timer_failure_is_detected_after_startup(self):
        from coder_agent_adhoc import godot_runtime as G
        from coder_agent_adhoc.gates import command_failed
        self.stage('godot')
        self.addCleanup(G.release_stage)
        f = C.GAME_DIR / 'main.gd'
        f.write_text('extends Node2D\nfunc _ready():\n    await get_tree().create_timer(5.0).timeout\n    get_node("MissingOnlyAfterFiveSeconds").call("tick")\n', encoding='utf-8')
        result = G.run_godot('boot')
        self.assertTrue(command_failed(result), result)
        self.assertIn('MissingOnlyAfterFiveSeconds', result['output'])
        self.assertEqual(result['observed']['simulation_frames'], 600, result)

    def test_native_healthy_delayed_timer_completes_observation(self):
        from coder_agent_adhoc import godot_runtime as G
        from coder_agent_adhoc.gates import command_failed
        self.stage('godot')
        self.addCleanup(G.release_stage)
        (C.GAME_DIR / 'main.gd').write_text('extends Node2D\nfunc _ready():\n    await get_tree().create_timer(5.0).timeout\n    print("DELAYED_CALLBACK_REALLY_RAN")\n', encoding='utf-8')
        result = G.run_godot('boot')
        self.assertFalse(command_failed(result), result)
        self.assertIn('DELAYED_CALLBACK_REALLY_RAN', result['output'])
        self.assertEqual(result['observed']['simulation_frames'], 600, result)

    def test_native_ui_event_exploration_reaches_real_button_callback(self):
        from coder_agent_adhoc import godot_runtime as G
        from coder_agent_adhoc.gates import command_failed
        self.stage('godot')
        self.addCleanup(G.release_stage)
        source = 'extends Node2D\nfunc _ready():\n    var button = Button.new()\n    button.text = "Play"\n    button.size = Vector2(120,60)\n    button.pressed.connect(on_pressed)\n    add_child(button)\nfunc on_pressed():\n    print("BUTTON_ACTUALLY_RECEIVED")\n'
        (C.GAME_DIR / 'main.gd').write_text(source, encoding='utf-8')
        result = G.run_godot('boot')
        self.assertFalse(command_failed(result), result)
        self.assertIn('BUTTON_ACTUALLY_RECEIVED', result['output'])
        self.assertEqual(result['observed']['button_events'], 1, result)

    def test_native_ui_callback_error_is_not_a_boot_pass(self):
        from coder_agent_adhoc import godot_runtime as G
        from coder_agent_adhoc.gates import command_failed
        self.stage('godot')
        self.addCleanup(G.release_stage)
        source = 'extends Node2D\nfunc _ready():\n    var button = Button.new()\n    button.text = "Play"\n    button.size = Vector2(120,60)\n    button.pressed.connect(on_pressed)\n    add_child(button)\nfunc on_pressed():\n    get_node("MissingOnlyWhenClicked").call("tick")\n'
        (C.GAME_DIR / 'main.gd').write_text(source, encoding='utf-8')
        result = G.run_godot('boot')
        self.assertTrue(command_failed(result), result)
        self.assertIn('MissingOnlyWhenClicked', result['output'])
        self.assertEqual(result['observed']['button_events'], 1, result)

    def test_tscn_comment_lexer_preserves_quoted_hashes_and_semicolon_comments(self):
        good = '[gd_scene format=3]\n[node name="Main" type="Label"]\ntext = ' + json.dumps('Color #fff and escaped "#"') + ' ; # legal comment\n'
        self.assertIsNone(godot.scene_text_problem(good, 'game/main.tscn'))
        bad = '[gd_scene format=3]\n[node name="Main" type="Node2D"]\nvisible = true # not a TSCN comment\n'
        issue = godot.scene_text_problem(bad, 'game/main.tscn')
        self.assertEqual(issue[0], 'godot_scene_comment')
        self.assertIn('game/main.tscn:3', issue[1])

    def test_tscn_hash_comment_rejected_before_write_or_native_execution(self):
        self.stage('godot')
        from coder_agent_adhoc.tools import tools_coder as T
        from coder_agent_adhoc import godot_runtime as G
        scene = C.GAME_DIR / 'main.tscn'
        before = scene.read_bytes()
        bad = '[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://main.gd" id="1"]\n[node name="Main" type="Node2D"]\nvisible = true # masks script binding\nscript = ExtResource("1")\n'
        with self.assertRaisesRegex(ValueError, 'godot_scene_comment'):
            T.write_file.invoke(dict(path='game/main.tscn', content=bad))
        self.assertEqual(scene.read_bytes(), before)
        scene.write_text(bad, encoding='utf-8')
        with patch.object(G, 'run_godot') as native:
            result = json.loads(T.run_shell.invoke(dict(argv=['boot'])))
        native.assert_not_called()
        self.assertEqual(result['reason'], 'godot_scene_comment')

    def test_native_ui_selection_then_world_click_reaches_action_callback(self):
        from coder_agent_adhoc import godot_runtime as G
        from coder_agent_adhoc.gates import command_failed
        self.stage('godot')
        self.addCleanup(G.release_stage)
        source = 'extends Node2D\nvar selected: bool = false\nfunc _ready():\n    var button = Button.new()\n    button.text = "Select"\n    button.size = Vector2(120,60)\n    button.pressed.connect(on_pressed)\n    add_child(button)\nfunc on_pressed():\n    selected = true\nfunc _input(event):\n    if selected and event is InputEventMouseButton and event.pressed:\n        get_node("MissingOnlyAfterSelectionAndWorldClick").call("tick")\n'
        (C.GAME_DIR / 'main.gd').write_text(source, encoding='utf-8')
        result = G.run_godot('boot')
        self.assertTrue(command_failed(result), result)
        self.assertIn('MissingOnlyAfterSelectionAndWorldClick', result['output'])
        self.assertEqual(result['observed']['world_points'], 2, result)

    def _native_button_child(self, child_filter, right=False):
        from coder_agent_adhoc import godot_runtime as G
        self.stage('godot')
        self.addCleanup(G.release_stage)
        source = 'extends Node2D\nfunc _ready():\n    var button = Button.new()\n    button.text = "Select"\n    button.size = Vector2(120,60)\n    button.button_mask = %d\n    button.pressed.connect(func(): print("CHILD_BUTTON_PRESSED"))\n    add_child(button)\n    var cover = TextureRect.new()\n    cover.size = Vector2(120,60)\n    cover.mouse_filter = %d\n    button.add_child(cover)\n' % (2 if right else 1, child_filter)
        (C.GAME_DIR / 'main.gd').write_text(source, encoding='utf-8')
        return G.run_godot('boot')

    def test_native_child_control_cannot_silently_swallow_button_click(self):
        from coder_agent_adhoc.gates import command_failed
        result = self._native_button_child(0)
        self.assertTrue(command_failed(result), result)
        self.assertIn('did not emit pressed', result['output'])
        self.assertNotIn('CHILD_BUTTON_PRESSED', result['output'])
        self.assertEqual(result['observed']['button_events'], 1, result)
        self.assertEqual(result['observed']['button_presses'], 0, result)

    def test_native_pointer_ignored_child_and_right_button_really_work(self):
        from coder_agent_adhoc.gates import command_failed
        result = self._native_button_child(2, right=True)
        self.assertFalse(command_failed(result), result)
        self.assertIn('CHILD_BUTTON_PRESSED', result['output'])
        self.assertEqual(result['observed']['button_presses'], 1, result)


if __name__ == '__main__':
    unittest.main()
