"""Offline tests for context compaction, patch tools, completion protocol and recovery records."""
import json
import unittest
from unittest.mock import patch
from langchain_core.messages import AIMessage, ToolMessage
import test_harness as H
from test_harness import Fake, call, calls, manual, write, INIT
from coder_agent_adhoc import agent_coder as A, contracts
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.context import compact
from coder_agent_adhoc.diagnostics import command_summary
from coder_agent_adhoc.run_context import CURRENT, RunContext
from coder_agent_adhoc.tools import tools_coder as T

BIG = '# filler line for compaction\n' * 200


class ContextAndTools(unittest.TestCase):
    setUp = H.Harness.setUp
    tearDown = H.Harness.tearDown
    stage = H.Harness.stage
    run_fake = H.Harness.run_fake

    def in_context(self, mode='repair'):
        ctx = RunContext(mode, contracts.plan())
        token = CURRENT.set(ctx)
        self.addCleanup(CURRENT.reset, token)
        return ctx

    # ---- compaction -------------------------------------------------------------
    def test_old_file_contents_are_not_resent(self):
        self.stage()
        source = (C.GAME_DIR / 'main.py').read_text(encoding='utf-8') + BIG
        with patch.object(C, 'CODER_MAX_STEPS', 5):
            result, fake = self.run_fake([calls(INIT, write('game/main.py', source)), call('read_plan', {}),
                                          call('read_plan', {}), call('read_plan', {}), manual()])
        self.assertEqual(result['status'], 'ready_for_testing', result)
        last = fake.inputs[-1]
        marker = 'filler line for compaction'
        self.assertNotIn(marker, json.dumps([m.model_dump() for m in last], default=str))
        self.assertIn(marker, json.dumps([m.model_dump() for m in fake.inputs[1]], default=str))
        # Every tool call in the compacted view still has its ToolMessage.
        ids = {c['id'] for m in last if isinstance(m, AIMessage) for c in m.tool_calls}
        answered = {m.tool_call_id for m in last if isinstance(m, ToolMessage)}
        self.assertEqual(ids, answered)

    def test_compact_keeps_recent_turns_verbatim(self):
        from langchain_core.messages import SystemMessage, HumanMessage
        messages = [SystemMessage(content='s'), HumanMessage(content='plan')]
        for i in range(4):
            messages.append(AIMessage(content='', tool_calls=[dict(name='write_file', id=f'c{i}', type='tool_call',
                                                                   args=dict(path='game/main.py', content=BIG))]))
            messages.append(ToolMessage(content='OK ' + 'y' * 1000, tool_call_id=f'c{i}'))
        view = compact(messages, recent_turns=2)
        self.assertIsInstance(view[2], __import__('langchain_core.messages', fromlist=['HumanMessage']).HumanMessage)
        self.assertIn('COMPLETED HISTORY', view[2].content)
        self.assertNotIn(BIG, view[2].content)
        self.assertEqual(view[-2].tool_calls[0]['args']['content'], BIG)
        self.assertLess(len(view[3].content), 600)
        self.assertEqual(messages[2].tool_calls[0]['args']['content'], BIG, 'history itself is unchanged')

    # ---- tools ------------------------------------------------------------------
    def test_multi_edit_patch_is_all_or_nothing(self):
        self.stage(); self.in_context()
        f = C.GAME_DIR / 'main.py'; before = f.read_bytes()
        T.read_file.invoke(dict(paths=['game/main.py']))
        with self.assertRaisesRegex(ValueError, 'edit 1 matched 0'):
            T.apply_patch.invoke(dict(path='game/main.py', edits=[dict(old='score > 3', new='score >= 3'),
                                                                  dict(old='no such text', new='x')]))
        self.assertEqual(f.read_bytes(), before)
        T.apply_patch.invoke(dict(path='game/main.py', edits=[dict(old='score > 3', new='score >= 3'),
                                                              dict(old='score = 0', new='score = 0  # start')]))
        text = f.read_text(encoding='utf-8')
        self.assertIn('score >= 3', text); self.assertIn('# start', text)

    def test_patch_preserves_crlf(self):
        self.stage(); self.in_context()
        f = C.GAME_DIR / 'main.py'
        f.write_bytes(f.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        T.read_file.invoke(dict(paths=['game/main.py']))
        T.apply_patch.invoke(dict(path='game/main.py', old='        if action == "q":\n            break',
                                  new='        if action == "q":\n            # quit\n            break'))
        data = f.read_bytes()
        self.assertNotIn(b'\n', data.replace(b'\r\n', b''))
        self.assertIn(b'# quit\r\n', data)

    def test_read_file_line_range(self):
        self.stage(); ctx = self.in_context()
        out = T.read_file.invoke(dict(paths=['game/main.py'], start_line=2, end_line=3))
        self.assertIn('(lines 2-3 of', out)
        self.assertEqual(len(out.splitlines()), 3)
        self.assertIn('game/main.py', ctx.read_versions)
        with self.assertRaisesRegex(ValueError, 'exactly_one_path'):
            T.read_file.invoke(dict(paths=['game/main.py', 'game/__init__.py'], start_line=1))

    def test_python_traceback_gets_source_context(self):
        self.stage()
        out = 'Traceback (most recent call last):\n  File "C:\\x\\traces\\py-runtime-1\\game\\main.py", line 9, in run_game\nNameError: x\n'
        summary = command_summary(dict(returncode=1, reason=None, output=out))
        self.assertIn('game/main.py:9', summary['source_context'])

    # ---- completion protocol / contracts ------------------------------------------
    def test_boot_before_manual_is_not_a_failure(self):
        self.stage(); source = (C.GAME_DIR / 'main.py').read_text(encoding='utf-8')
        result, _ = self.run_fake([calls(INIT, write('game/main.py', source), ('run_shell', dict(argv=['boot']))), manual()])
        self.assertEqual(result['status'], 'ready_for_testing', result)
        self.assertEqual(result['debug_statistics']['local_failure_events'], 0)

    def test_coverage_alongside_final_tool_call_is_recorded(self):
        self.stage(); source = (C.GAME_DIR / 'main.py').read_text(encoding='utf-8')
        claim = json.dumps(dict(coverage=[dict(index=0, files=['game/main.py'], summary='win at 3', limitations=[]),
                                          dict(index=1, files=['game/main.py'], summary='ongoing below 3', limitations=[])]))
        final = AIMessage(content=claim, tool_calls=manual().tool_calls)
        result, _ = self.run_fake([calls(INIT, write('game/main.py', source)), final])
        self.assertEqual(result['coverage_status'], 'provided')
        self.assertEqual(result['requirement_coverage'][0]['coverage_evidence'], 'model_claim_unverified')

    def test_missing_package_marker_blocks_build_before_model(self):
        self.stage(); p = json.loads(C.PLAN_FILE.read_text(encoding='utf-8'))
        p['architecture']['files'] = p['architecture']['files'][1:]
        C.PLAN_FILE.write_text(json.dumps(p))
        with patch.object(A, 'create_model') as model:
            result = A.run_coder()
        model.assert_not_called()
        self.assertIn('package_marker_must_be_first', result['reason'])

    def test_terminal_render_settings_only_warn(self):
        self.stage(); p = json.loads(C.PLAN_FILE.read_text(encoding='utf-8'))
        p['architecture']['resolution'] = dict(width=640, height=480); p['architecture']['fps'] = 30
        C.PLAN_FILE.write_text(json.dumps(p))
        result = A.run_coder(dry_run=True)
        self.assertEqual(result['status'], 'dry_run')
        self.assertIn('terminal_render_settings_ignored', result['plan_compatibility_warnings'])

    # ---- repair context and recovery ----------------------------------------------
    def test_repair_context_has_evidence_excerpt_and_regression_guard(self):
        fb = self.stage()
        result, fake = self.run_fake([AIMessage(content='inspect only')], 'repair', fb)
        first = json.loads(fake.inputs[0][1].content)
        failure = first['validator_feedback']['failures'][0]
        self.assertIn('evidence_excerpt', failure)
        guard = first['regression_guard']
        self.assertTrue(guard['previously_passed_test_ids'])
        failing = {f['requirement_index'] for f in first['validator_feedback']['failures']}
        self.assertTrue(all(r['index'] not in failing for r in guard['requirements_to_preserve']))
        self.assertIn('REPAIR', fake.inputs[0][0].content)
        self.assertNotIn('MODE: INITIAL BUILD', fake.inputs[0][0].content)

    def test_killed_attempt_is_recorded_as_aborted(self):
        self.stage()
        C.TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        C.TRACE_FILE.write_text(json.dumps(dict(ts=0, attempt_id='dead-attempt', event='start', mode='repair')) + '\n')
        result, _ = self.run_fake([AIMessage(content='done')])
        events = [json.loads(line) for line in C.TRACE_FILE.read_text(encoding='utf-8').splitlines()]
        aborted = [e for e in events if e['event'] == 'aborted']
        self.assertEqual([e['aborted_attempt_id'] for e in aborted], ['dead-attempt'])
        # The record is written once, not on every later run.
        self.run_fake([AIMessage(content='done')])
        events = [json.loads(line) for line in C.TRACE_FILE.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(sum(e['event'] == 'aborted' for e in events), 1)

    def test_repair_self_debug_counts_one_external_invocation(self):
        fb = self.stage()
        with patch.object(C, 'CODER_MAX_STEPS', 6):
            result, _ = self.run_fake([call('read_file', dict(paths=['game/main.py'])),
                                       call('apply_patch', dict(path='game/main.py', old='score > 3', new='score >>= 3')),
                                       call('run_shell', dict(argv=['syntax'])),
                                       call('apply_patch', dict(path='game/main.py', old='score >>= 3', new='score >= 3')),
                                       manual()], 'repair', fb)
        self.assertEqual(result['status'], 'ready_for_testing', result)
        stats = result['debug_statistics']
        self.assertEqual(stats['external_repair_invocations'], 1)
        self.assertGreaterEqual(stats['local_failure_events'], 1)
        self.assertEqual(stats['self_debug_attempts'], 1)


if __name__ == '__main__':
    unittest.main()
