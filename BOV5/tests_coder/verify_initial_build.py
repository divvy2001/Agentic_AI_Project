"""Opt-in live Initial Build acceptance in a new, isolated project directory."""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
def verify(renderer, destination):
    load_dotenv(ROOT/'.env')
    if not os.getenv('CODER_OPENROUTER_API_KEY'):
        raise RuntimeError('NOT RUN: CODER_OPENROUTER_API_KEY missing')
    destination=destination.resolve()
    if destination.exists(): raise FileExistsError('Use a NEW destination')
    destination.mkdir(parents=True)
    shutil.copytree(ROOT/'coder_agent_adhoc',destination/'coder_agent_adhoc',ignore=shutil.ignore_patterns('__pycache__'))
    (destination/'plans').mkdir()
    shutil.copy2(ROOT/'tests_coder/fixtures'/renderer/'coder_plan.json',destination/'plans/coder_plan.json')
    before=(destination/'plans/coder_plan.json').read_bytes()
    env=os.environ.copy();env['CODER_ISOLATED_RUN']='1';env['PYTHONIOENCODING']='utf-8'
    for name in ('PLANNER_OPENROUTER_API_KEY','ASSET_OPENROUTER_API_KEY','OPENROUTER_API_KEY','OPENAI_API_KEY'):env.pop(name,None)
    code="from coder_agent_adhoc.initial_build import run_initial_build; import json; from pathlib import Path; r=run_initial_build(); Path('coder_outcome.json').write_text(json.dumps(r,indent=2),encoding='utf-8')"
    r=subprocess.run([sys.executable,'-c',code],cwd=destination,env=env,capture_output=True,text=True,encoding='utf-8',timeout=1800)
    (destination/'invocation.log').write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
    if r.returncode: raise RuntimeError('Coder subprocess failed; see invocation.log')
    result=json.loads((destination/'coder_outcome.json').read_text(encoding='utf-8'))
    if (destination/'plans/coder_plan.json').read_bytes()!=before: raise AssertionError('Planner input changed')
    if result['status']!='ready_for_testing': raise AssertionError(result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print('PASS: build/startup gates only. Gameplay evaluation NOT RUN.')
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--renderer',required=True,choices=('terminal','pygame','godot'))
    parser.add_argument('--dest',required=True,type=Path)
    args=parser.parse_args();verify(args.renderer,args.dest)
