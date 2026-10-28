"""Counterexamples from the real 2026-10-25 failures; no paid requests."""
import copy,json,os,unittest
from unittest.mock import patch
from langchain_core.messages import AIMessage,HumanMessage,SystemMessage,ToolMessage
import test_harness as H
from coder_agent_adhoc import agent_coder as A,contracts
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.context import compact
from coder_agent_adhoc.run_context import CURRENT,RunContext
from coder_agent_adhoc.tools import tools_coder as T

class LiveFailures(unittest.TestCase):
    setUp=H.Harness.setUp
    tearDown=H.Harness.tearDown
    stage=H.Harness.stage
    run_fake=H.Harness.run_fake

    def context(self):
        ctx=RunContext('repair',contracts.plan());token=CURRENT.set(ctx)
        self.addCleanup(CURRENT.reset,token);return ctx

    def test_old_writes_are_not_executable_placeholder_calls(self):
        source='print("real source")\n'*100
        messages=[SystemMessage(content='s'),HumanMessage(content='p')]
        for i in range(5):
            messages.extend([AIMessage(content='',tool_calls=[dict(name='write_file',args=dict(path='game/main.py',content=source),id=str(i),type='tool_call')]),ToolMessage(content='OK',tool_call_id=str(i))])
        original=copy.deepcopy(messages);view=compact(messages,recent_turns=2)
        self.assertEqual(messages,original)
        self.assertEqual([c['id'] for m in view if isinstance(m,AIMessage) for c in m.tool_calls],['3','4'])
        self.assertEqual([m.tool_call_id for m in view if isinstance(m,ToolMessage)],['3','4'])
        self.assertNotIn('[omitted',json.dumps([m.model_dump() for m in view]))
        self.assertLess(len(json.dumps([m.model_dump() for m in view])),len(json.dumps([m.model_dump() for m in messages]))*.65)

    def test_summary_write_rejected_without_file_or_history_change(self):
        self.stage();ctx=self.context();f=C.GAME_DIR/'main.py';original=f.read_bytes()
        T.read_file.invoke(dict(paths=['game/main.py']))
        with self.assertRaisesRegex(ValueError,'context_summary_is_not_source'):
            T.write_file.invoke(dict(path='game/main.py',content='[omitted 5163 chars sha256:e7b246094478; the file on disk is authoritative, use read_file to see it]',reason='regression reproduction'))
        self.assertEqual(f.read_bytes(),original);self.assertFalse(ctx.changes)

    def test_latest_read_survives_compaction_until_successful_write(self):
        messages=[SystemMessage(content='s'),HumanMessage(content='p')]
        source='=== game/main.py ===\ndef keep_this_exact_indentation():\n\treturn 42\n'
        messages.extend([H.call('read_file',dict(paths=['game/main.py'])),ToolMessage(content=source,tool_call_id='call-read_file')])
        for i in range(4):messages.extend([H.call('read_plan',{}),ToolMessage(content='{}',tool_call_id='call-read_plan')])
        view=compact(messages,recent_turns=2)
        self.assertIn(source,view[2].content)
        messages.extend([H.call('apply_patch',dict(path='game/main.py',old='42',new='43')),ToolMessage(content='OK: patched',tool_call_id='call-apply_patch')])
        view=compact(messages,recent_turns=2)
        self.assertNotIn('LATEST READ SOURCE DATA',view[2].content)

    def test_compacted_plan_preserves_hard_requirements_and_original(self):
        requirement=dict(text='WASD moves player',check='D changes x',status='full',priority='core',milestone=1,quote='WASD moves player')
        payload=dict(plan=dict(requirements=[requirement],architecture=dict(entry_point='game/main.py')))
        first=HumanMessage(content=json.dumps(payload));messages=[SystemMessage(content='s'),first]
        for i in range(4):messages.extend([H.call('read_plan',{}),ToolMessage(content='{}',tool_call_id='call-read_plan')])
        view=compact(messages,recent_turns=2);actual=json.loads(view[1].content)['plan']['requirements'][0]
        self.assertEqual(actual,{k:v for k,v in requirement.items() if k!='quote'})
        self.assertEqual(json.loads(first.content),payload)

    def test_patch_cannot_insert_compaction_placeholder(self):
        self.stage();self.context();f=C.GAME_DIR/'main.py';original=f.read_bytes()
        T.read_file.invoke(dict(paths=['game/main.py']))
        with self.assertRaisesRegex(ValueError,'context_summary_is_not_source'):
            T.apply_patch.invoke(dict(path='game/main.py',old='score > 3',new='[omitted 999 chars sha256:abc; use read_file]'))
        self.assertEqual(f.read_bytes(),original)

    def test_null_fps_uses_documented_default_without_plan_mutation(self):
        self.stage('pygame');p=json.loads(C.PLAN_FILE.read_text(encoding='utf-8'));p['architecture']['fps']=None
        C.PLAN_FILE.write_text(json.dumps(p),encoding='utf-8');before=C.PLAN_FILE.read_bytes()
        result=A.run_coder(dry_run=True)
        self.assertEqual(result['status'],'dry_run',result)
        self.assertEqual(result['runtime_render_settings']['fps'],60)
        self.assertIn('graphical_fps_unspecified_using_planner_default_60',result['plan_compatibility_warnings'])
        self.assertEqual(C.PLAN_FILE.read_bytes(),before)
        for bad in (True,-1,'60',241):
            p['architecture']['fps']=bad
            with self.assertRaisesRegex(ValueError,'graphical_resolution_and_fps_required'):contracts.file_contract(p)

    def test_provider_error_stops_before_synthetic_game_failures(self):
        self.stage();response=AIMessage(content='',response_metadata=dict(finish_reason='error'))
        result,fake=self.run_fake([response])
        self.assertIn('provider_response_error',result['reason']);self.assertEqual(len(fake.inputs),1)
        self.assertEqual(result['debug_statistics']['local_failure_events'],0)
        self.assertEqual(result['smoke']['plan_and_files'],'not_run')

    def test_known_billing_provider_error_retries_at_most_once(self):
        self.stage();response=AIMessage(content='',response_metadata=dict(finish_reason='error',token_usage=dict(cost=0)),
                                       usage_metadata=dict(input_tokens=1,output_tokens=0,total_tokens=1))
        result,fake=self.run_fake([response,response,response])
        self.assertEqual(len(fake.inputs),2);self.assertEqual(result['provider_error_retries'],1)
        self.assertEqual(result['usage']['calls'],2);self.assertIn('provider_response_error',result['reason'])
        self.assertFalse(any(isinstance(m,AIMessage) for m in fake.inputs[1]))
        self.assertIn('ONE valid tool call',fake.inputs[1][-1].content)

    def test_trace_budget_numbers_remain_valid_json_and_secrets_redacted(self):
        self.stage()
        with patch.dict(os.environ,{'CODER_MAX_TOKENS':'180000','DEMO_API_KEY':'secret-value-for-regression'}):
            A.trace(dict(event='regression',tokens=180000,note='secret-value-for-regression'))
        row=json.loads(C.TRACE_FILE.read_text().splitlines()[-1]);self.assertEqual(row['tokens'],180000)
        self.assertEqual(row['note'],'[REDACTED]')

    def test_opaque_asset_warning_preserves_upstream_bytes(self):
        self.stage();p=contracts.plan();p['architecture']['assets']['sprites']=[dict(id='hero',description='transparent background',width=64,height=64)]
        from PIL import Image
        f=C.GAME_DIR/'assets/hero.png';f.parent.mkdir(exist_ok=True);Image.new('RGBA',(64,64),(20,40,60,255)).save(f)
        before=f.read_bytes();assets=[dict(id='hero',path='game/assets/hero.png')]
        warning=contracts.asset_quality_warnings(p,assets)
        self.assertEqual(warning[0]['issue'],'transparent_requested_but_image_fully_opaque');self.assertEqual(f.read_bytes(),before)
        Image.new('RGBA',(64,64),(0,0,0,0)).save(f)
        self.assertEqual(contracts.asset_quality_warnings(p,assets),[])

if __name__=='__main__':unittest.main()
