"""Offline integration of the real tool loop and smoke gates; no API calls."""
import json, os, shutil, tempfile, unittest, sys
from pathlib import Path
from unittest.mock import patch
from langchain_core.messages import AIMessage
from coder_agent_adhoc import agent_coder as A, repair
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc import contracts, execution
from coder_agent_adhoc.tools import tools_coder as T

FIX=Path(__file__).parent/'fixtures'

def call(name,args):
    return AIMessage(content='',tool_calls=[dict(name=name,args=args,id='call-'+name,type='tool_call')])
def calls(*pairs,content=''):
    """One model turn with several tool calls (unique ids)."""
    return AIMessage(content=content,tool_calls=[dict(name=n,args=a,id=f'call-{i}-{n}',type='tool_call') for i,(n,a) in enumerate(pairs)])
def manual():
    return call('write_play_manual',dict(test_input='1\\n1\\n1\\n',expected_win_output='WIN',expected_lose_output='',notes='score three times'))
def write(name,content):
    return ('write_file',dict(path=name,content=content))
INIT=write('game/__init__.py','')

class Fake:
    def __init__(self,messages): self.responses=iter(messages); self.inputs=[]
    def invoke(self,messages):
        self.inputs.append(list(messages))
        return next(self.responses,AIMessage(content='finished'))

class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.patches=[]
        q=patch.object(C,'CODER_MAX_STEPS',4);q.start();self.patches.append(q)
        for name,sub in [('ROOT',''),('GAME_DIR','game'),('PLAN_FILE','plans/coder_plan.json'),('ASSET_MANIFEST_FILE','plans/asset_manifest.json'),('PLAY_MANUAL_FILE','plans/play_manual.json'),('TRACE_FILE','traces/coder_attempts.jsonl')]:
            q=patch.object(C,name,self.root/sub); q.start(); self.patches.append(q)
        q=patch.object(C,'CODER_OPENROUTER_API_KEY','fake-offline-key'); q.start(); self.patches.append(q)
        q=patch.dict(os.environ,{'CODER_ISOLATED_RUN':'1'});q.start();self.patches.append(q)
        for name,sub in [('ROOT',''),('GAME_DIR','game'),('PLAN_FILE','plans/coder_plan.json')]:
            q=patch.object(repair,name,self.root/sub);q.start();self.patches.append(q)
        (self.root/'coder_agent_adhoc').mkdir()
        shutil.copy2(Path(A.__file__).parent/'smoke_child.py',self.root/'coder_agent_adhoc/smoke_child.py')
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()
    def stage(self,r='terminal'):
        f=FIX/r; (self.root/'plans').mkdir(exist_ok=True)
        shutil.copy2(f/'coder_plan.json',C.PLAN_FILE); shutil.copytree(f/'game',C.GAME_DIR)
        dest=self.root/'traces/eval/eval-v1'; dest.mkdir(parents=True)
        shutil.copy2(f/'feedback.json',dest/'test_results.json'); shutil.copy2(f/'traces/eval/eval-v1/T03.log',dest/'T03.log')
        return 'traces/eval/eval-v1/test_results.json'
    def run_fake(self,responses,mode='initial_build',feedback=None):
        fake=Fake(responses)
        with patch.object(A,'create_model',return_value=fake): result=A.run_coder(mode=mode,feedback_path=feedback)
        return result,fake
    def test_terminal_real_loop_patch_and_regression(self):
        fb=self.stage(); f=C.GAME_DIR/'main.py'; text=f.read_text(encoding='utf-8')
        self.assertIn('score > 3',text)
        result,fake=self.run_fake([call('read_file',{'paths':['game/main.py']}),call('apply_patch',{'path':'game/main.py','old':'score > 3','new':'score >= 3'}),manual(),AIMessage(content='fixed')],'repair',fb)
        self.assertEqual(result['status'],'ready_for_testing',result)
        self.assertTrue(all(x=='passed' for x in result['smoke'].values()))
        self.assertEqual(f.read_text(encoding='utf-8'),text.replace('score > 3','score >= 3'))
        tool_messages=[m for ms in fake.inputs for m in ms if m.type=='tool']
        self.assertTrue(tool_messages)
        import subprocess
        for which in ('behavior','regression'):
            t=FIX/'terminal/tests'/('test_'+which+'.py')
            # Frozen scripts resolve their own workspace, so copy without changing bytes.
            (self.root/'eval_tests').mkdir(exist_ok=True); shutil.copy2(t,self.root/'eval_tests'/t.name)
            r=subprocess.run([sys.executable,str(self.root/'eval_tests'/t.name)],cwd=self.root,capture_output=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_no_tools_never_ready_for_missing_outputs(self):
        self.stage(); result,_=self.run_fake([AIMessage(content='done')])
        self.assertNotEqual(result['status'],'ready_for_testing')
        self.assertIn('stagnated',result['reason'])
    def test_manual_alone_never_ready_for_initial_build(self):
        self.stage(); result,_=self.run_fake([manual()]); self.assertNotEqual(result['status'],'ready_for_testing')
    def test_syntax_failure_cannot_finish(self):
        self.stage(); result,_=self.run_fake([calls(INIT,write('game/main.py','def broken(:')),manual()])
        self.assertEqual(result['smoke']['syntax_or_import'],'failed')
    def test_boot_failure_cannot_finish(self):
        fb=self.stage();result,_=self.run_fake([call('read_file',{'paths':['game/main.py']}),call('write_file',{'path':'game/main.py','content':"raise RuntimeError('broken')",'reason':'exercise runtime failure gate'}),manual()],'repair',fb)
        self.assertEqual(result['smoke']['boot'],'failed')
    def test_tool_error_returns_toolmessage(self):
        fb=self.stage(); result,fake=self.run_fake([call('apply_patch',{'path':'game/main.py','old':'nonexistent','new':'x'}),AIMessage(content='done')],'repair',fb)
        self.assertTrue(any('patch_context' in str(m.content) for ms in fake.inputs for m in ms if m.type=='tool'))
        self.assertNotEqual(result['status'],'ready_for_testing')
    def test_invalid_feedback_and_wrong_stages_no_model_no_writes(self):
        fb=self.stage(); f=self.root/fb; original=json.loads(f.read_text()); original_game=(C.GAME_DIR/'main.py').read_bytes(); original_plan=C.PLAN_FILE.read_bytes()
        variants=[]
        for stage in ('planner','asset','runtime_eval_generator','unknown'):
            variants.append(dict(original,failing_stage=stage))
        variants += [dict(original,status='inconclusive',failing_stage='unknown',failures=[]),dict(original,suite_version='other')]
        bad=json.loads(json.dumps(original)); bad['failures'][0]['requirement_index']=999; variants.append(bad)
        bad=json.loads(json.dumps(original)); bad['failures'][0]['evidence_path']='../outside'; variants.append(bad)
        for v in variants:
            f.write_text(json.dumps(v))
            with patch.object(A,'create_model') as model:
                r=repair.run_repair(fb); self.assertEqual(r['status'],'blocked'); model.assert_not_called()
            self.assertEqual((C.GAME_DIR/'main.py').read_bytes(),original_game);self.assertEqual(C.PLAN_FILE.read_bytes(),original_plan)
        f.write_text('{bad json'); self.assertIn('invalid_feedback',repair.run_repair(fb)['reason'])
        f.write_text(json.dumps(original)); (f.parent/'T03.log').unlink(); self.assertIn('invalid_feedback',repair.run_repair(fb)['reason'])
    def test_paths_commands_and_secret_reads_rejected(self):
        self.stage()
        for name in ('../config.py','game/../../config.py','C:/secret','.env','game/../plans/coder_plan.json'):
            with self.assertRaises(ValueError): T.write_file.invoke(dict(path=name,content='x'))
        with self.assertRaises(ValueError): T.read_file.invoke(dict(paths=['.env']))
        with self.assertRaises(ValueError): T.run_shell.invoke(dict(argv=['pip','install','anything']))
        with self.assertRaises(ValueError): T.write_file.invoke(dict(path='game/tests/test.py',content=''))
        with self.assertRaises(ValueError): T.write_file.invoke(dict(path='game/unplanned.py',content=''))
    def test_none_and_procedural_ignore_stale_manifest(self):
        self.stage(); C.ASSET_MANIFEST_FILE.write_text('{bad')
        p=contracts.plan();self.assertEqual(contracts.assets(p),[])
        p['architecture']['assets']['strategy']='procedural';self.assertEqual(contracts.assets(p),[])
    def test_ai_art_required_and_dimensions(self):
        from PIL import Image
        self.stage(); p=contracts.plan(); p['architecture']['assets']=dict(strategy='ai_art',sprites=[dict(id='x',width=16,height=16)])
        with self.assertRaisesRegex(ValueError,'asset_missing'): contracts.assets(p)
        m=dict(task_id=p['game_title'],framework='terminal',assets=[dict(id='x',path='game/x.png',required=True,generation_status='generated',validation_status='passed')])
        C.ASSET_MANIFEST_FILE.write_text(json.dumps(m));Image.new('RGB',(8,8)).save(C.GAME_DIR/'x.png')
        with self.assertRaisesRegex(ValueError,'dimensions'):contracts.assets(p)
        Image.new('RGB',(16,16)).save(C.GAME_DIR/'x.png');self.assertEqual(len(contracts.assets(p)),1)
    def test_three_renderer_contracts_and_fallback(self):
        self.stage()
        for renderer in ('terminal','pygame','godot'):
            p=json.loads((FIX/renderer/'coder_plan.json').read_text(encoding='utf-8'));p['status']='fallback';p['requirements'][0]['status']='approximated'
            C.PLAN_FILE.write_text(json.dumps(p)); r=A.run_coder(dry_run=True)
            self.assertEqual(r['status'],'dry_run');self.assertEqual(len(r['approximated_requirements']),1);self.assertEqual(r['planner_status'],'fallback')
    def test_child_env_and_output_timeout_limits(self):
        with patch.dict(os.environ,{'CODER_OPENROUTER_API_KEY':'never-child','AWS_SECRET_ACCESS_KEY':'also-never'}):
            env=execution.child_env();self.assertNotIn('CODER_OPENROUTER_API_KEY',env);self.assertNotIn('AWS_SECRET_ACCESS_KEY',env)
        self.assertNotIn('CODER_SMOKE_FRAMES',env)
        # Sandboxed game runs are bounded in time and output.
        self.stage(); p=contracts.plan()
        (C.GAME_DIR/'main.py').write_text('while True:\n    pass\n')
        with patch.object(C,'COMMAND_TIMEOUT',2): r=execution.run_action(p,'boot')
        self.assertEqual(r['reason'],'timeout')
        (C.GAME_DIR/'main.py').write_text("while True:\n    print('x'*1000)\n")
        r=execution.run_action(p,'boot')
        self.assertEqual(r['reason'],'output_limit');self.assertLessEqual(len(r['output']),C.OUTPUT_LIMIT)
    def test_pygame_early_exit_rejected(self):
        fb=self.stage('pygame'); result,_=self.run_fake([call('read_file',{'paths':['game/main.py']}),call('write_file',{'path':'game/main.py','content':'import pygame\npygame.init()\npygame.quit()\n','reason':'exercise early exit rejection'}),manual()],'repair',fb)
        self.assertEqual(result['smoke']['boot'],'failed')
    def test_protected_plan_change_detected(self):
        from coder_agent_adhoc.gates import smoke
        self.stage(); old=C.PLAN_FILE.read_bytes();p=contracts.plan();C.PLAN_FILE.write_text('{}')
        gates,_,reason=smoke(p,{'plans/coder_plan.json':old},set(),'repair')
        self.assertIn('protected_input_changed',reason)

    def test_full_25_round_budget(self):
        self.stage(); fake=Fake([call('read_plan',{}) for _ in range(25)])
        with patch.object(C,'CODER_MAX_STEPS',25),patch.object(A,'create_model',return_value=fake):
            r=A.run_coder()
        self.assertEqual(r['status'],'budget_exhausted');self.assertEqual(r['steps'],25);self.assertEqual(len(fake.inputs),25)
    def test_model_failure_is_structured(self):
        self.stage()
        with patch.object(A,'create_model') as factory:
            factory.return_value.invoke.side_effect=RuntimeError('transport failed')
            r=A.run_coder()
        self.assertEqual(r['status'],'blocked');self.assertIn('model_error',r['reason'])
    def test_missing_godot_blocks_without_false_pass(self):
        self.stage('godot')
        from coder_agent_adhoc.gates import smoke
        p=contracts.plan()
        with patch.dict(os.environ,{'GODOT_BINARY':''}),patch('shutil.which',return_value=None):
            gates,_,reason=smoke(p,{},set(),'repair')
        self.assertIn('runtime_unavailable',reason);self.assertNotEqual(gates['boot'],'passed')
    def test_godot_error_with_zero_exit_rejected(self):
        self.stage('godot')
        from coder_agent_adhoc.gates import smoke
        with patch('coder_agent_adhoc.gates.run_action',return_value=dict(returncode=0,reason=None,output='SCRIPT ERROR: Parse Error: broken')):
            gates,_,reason=smoke(contracts.plan(),{},set(),'repair')
        self.assertEqual(gates['syntax_or_import'],'failed')
    def test_godot_main_scene_cannot_drift(self):
        self.stage('godot'); (C.GAME_DIR/'project.godot').write_text('[application]\nrun/main_scene="res://wrong.tscn"')
        from coder_agent_adhoc.gates import smoke
        self.assertEqual(smoke(contracts.plan(),{},set(),'repair')[2],'project_main_scene_mismatch')
    def test_pygame_unbounded_loop_observed_and_stopped(self):
        fb=self.stage('pygame')
        source="import pygame\npygame.init()\nscreen=pygame.display.set_mode((64,64))\nwhile True:\n    screen.fill((0,0,0))\n    pygame.display.flip()\n"
        r,_=self.run_fake([call('read_file',dict(paths=['game/main.py'])),call('write_file',dict(path='game/main.py',content=source,reason='exercise a bounded real display loop')),manual(),AIMessage(content='coverage')],'repair',fb)
        self.assertEqual(r['status'],'ready_for_testing',r)
    def test_game_secret_read_and_network_denied(self):
        fb=self.stage()
        for source in ("import socket\ns=socket.socket()\ns.connect(('example.com',80))\n", "from pathlib import Path\nx=Path('../.env').read_text()\nprint(x)\n"):
            r,_=self.run_fake([call('read_file',dict(paths=['game/main.py'])),call('write_file',dict(path='game/main.py',content=source,reason='exercise isolation rejection')),manual()],'repair',fb)
            self.assertNotEqual(r['status'],'ready_for_testing')
    def test_malformed_plan_never_calls_model(self):
        self.stage(); original=json.loads(C.PLAN_FILE.read_text(encoding='utf-8'))
        for field,value in [('status','invalid'),('profile',{'renderer':{'value':'pygame'}}),('requirements',[])]:
            p=dict(original);p[field]=value;C.PLAN_FILE.write_text(json.dumps(p))
            with patch.object(A,'create_model') as model:
                r=A.run_coder();model.assert_not_called();self.assertEqual(r['status'],'blocked')

if __name__=='__main__':unittest.main()
