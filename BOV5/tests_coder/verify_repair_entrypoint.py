"""Opt-in acceptance for Codex AFTER implementing Repair; not part of default unit suite.

--mode negative: no key needed; wrong-stage must block without changing code.
--mode live: uses personal CODER_OPENROUTER_API_KEY, bills OpenRouter, runs before/after frozen tests.

Runs against a disposable project assembled from fixtures. Original V3 game is untouched.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from prepare_repair_workspace import prepare


def sha_tree(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name != 'play_manual.json'
    }


def run_frozen(workspace, renderer, test):
    if renderer == 'godot':
        godot = os.getenv('GODOT_BINARY') or shutil.which('godot') or shutil.which('godot4')
        if not godot:
            raise RuntimeError('SKIPPED: Godot is not installed; no game-test PASS claim')
        cmd = [godot, '--headless', '--path', 'game', '--script', f'res://tests/test_{test}.gd']
    else:
        cmd = [sys.executable, f'eval_tests/test_{test}.py']
    safe_env={k:os.environ[k] for k in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','APPDATA','LOCALAPPDATA','USERPROFILE') if k in os.environ}
    return subprocess.run(cmd, cwd=workspace, env=safe_env, capture_output=True, text=True, encoding='utf-8', timeout=30)


def run_coder_subprocess(workspace, mode):
    env = os.environ.copy()
    env.pop('PLANNER_OPENROUTER_API_KEY', None)
    env.pop('ASSET_OPENROUTER_API_KEY', None)
    env.pop('OPENROUTER_API_KEY', None)
    code = """import json
from coder_agent_adhoc.repair import run_repair
result=run_repair('traces/eval/eval-v1/test_results.json')
print('CODER_RESULT_JSON='+json.dumps(result, ensure_ascii=False))
"""
    r = subprocess.run([sys.executable, '-c', code], cwd=workspace, env=env,
                       capture_output=True, text=True, encoding='utf-8', timeout=600)
    value = None
    for line in r.stdout.splitlines():
        if line.startswith('CODER_RESULT_JSON='):
            value = json.loads(line[len('CODER_RESULT_JSON='):])
    if r.returncode or value is None:
        raise AssertionError(f'Coder did not return a structured result (not implemented / error):\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return value


def verify(renderer, mode):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    if mode == 'live' and not os.getenv('CODER_OPENROUTER_API_KEY'):
        raise RuntimeError('LIVE NOT RUN: Set CODER_OPENROUTER_API_KEY explicitly')
    with tempfile.TemporaryDirectory(prefix=f'pe6203_{renderer}_repair_') as td:
        workspace = prepare(renderer, Path(td) / 'project')
        feedback_path = workspace / 'traces/eval/eval-v1/test_results.json'
        before = sha_tree(workspace / 'game')
        before_plans = sha_tree(workspace / 'plans')
        pre_fail = run_frozen(workspace, renderer, 'behavior')
        pre_pass = run_frozen(workspace, renderer, 'regression')
        if pre_fail.returncode == 0 or pre_pass.returncode != 0:
            raise AssertionError('Fixture precondition is not T03 FAIL / T01 PASS')
        if mode == 'negative':
            base_feedback = json.loads(feedback_path.read_text(encoding='utf-8'))
            for failing_stage in ('asset', 'planner', 'runtime_eval_generator', 'unknown', 'inconclusive'):
                feedback = json.loads(json.dumps(base_feedback))
                if failing_stage == 'inconclusive':
                    feedback['status'] = 'inconclusive'
                    feedback['failing_stage'] = 'unknown'
                    feedback['failures'] = []
                else:
                    feedback['failing_stage'] = failing_stage
                    if failing_stage == 'asset':
                        feedback['failures'][0]['error_category'] = 'asset'
                    elif failing_stage == 'runtime_eval_generator':
                        feedback['failures'][0]['error_category'] = 'test_definition'
                    elif failing_stage == 'planner':
                        feedback['failures'][0]['error_category'] = 'spec'
                    feedback['failures'][0]['attribution_evidence'] = 'Synthetic negative-routing fixture only.'
                feedback_path.write_text(json.dumps(feedback, indent=2) + '\n', encoding='utf-8')
                result = run_coder_subprocess(workspace, mode)
                if result.get('status') != 'blocked' or sha_tree(workspace / 'game') != before:
                    raise AssertionError(f'Wrong-stage {failing_stage} changed code / did not block: {result}')
                if sha_tree(workspace / 'plans') != before_plans:
                    raise AssertionError(f'Wrong-stage {failing_stage} changed Planner artifacts')
            print('PASS: asset/planner/eval/unknown/inconclusive blocked without source changes')
            return
        result = run_coder_subprocess(workspace, mode)
        after = sha_tree(workspace / 'game')
        if sha_tree(workspace / 'plans') != before_plans:
            raise AssertionError('Coder modified Planner artifacts')
        if result.get('status') != 'ready_for_testing':
            raise AssertionError(f'Coder did not reach internal ready_for_testing: {result}')
        if before == after:
            raise AssertionError('No game source change after Repair')
        post_fail = run_frozen(workspace, renderer, 'behavior')
        post_regression = run_frozen(workspace, renderer, 'regression')
        if post_fail.returncode or post_regression.returncode:
            raise AssertionError('Repair failed frozen behavior/regression tests:\n'
                                 + post_fail.stdout + post_fail.stderr + post_regression.stdout + post_regression.stderr)
        print('PASS: T03 FAIL→PASS and T01 remained PASS; internal status ready_for_testing')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--renderer', required=True, choices=['terminal', 'pygame', 'godot'])
    ap.add_argument('--mode', required=True, choices=['negative', 'live'])
    args = ap.parse_args()
    try:
        verify(args.renderer, args.mode)
    except (AssertionError, RuntimeError, TypeError, subprocess.TimeoutExpired) as e:
        print(f'FAILED / NOT IMPLEMENTED / SKIPPED: {e}', file=sys.stderr)
        sys.exit(1)
