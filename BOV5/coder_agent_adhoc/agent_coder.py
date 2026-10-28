"""Shared bounded LangChain/OpenRouter harness for Initial Build and Repair.

Model -> tool calls -> local execution -> ToolMessage, repeated within budgets. Only the
harness's own T1-T3 gates can produce ready_for_testing; ready is never gameplay PASS.
"""
import json, os, sys, time
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.contracts import plan, assets, path, file_contract, missing_dependencies, asset_quality_warnings, render_settings
from coder_agent_adhoc.gates import smoke, file_inventory, command_failed
from coder_agent_adhoc.gates import smoke as integration_smoke
from coder_agent_adhoc.context import initial_messages, compact, remember_initial_notes, update_build_progress
from coder_agent_adhoc.tools import tools_coder as T
from coder_agent_adhoc.tools.tools_asset import list_assets
from coder_agent_adhoc.workspace import prepare_initial_workspace
from coder_agent_adhoc.diagnostics import smoke_summary, command_summary, summarize_local_failure, extract_validator_issues
from coder_agent_adhoc.run_context import CURRENT, RunContext, workspace_lock, digest
from coder_agent_adhoc import build_state

TOOLS = [T.read_plan, list_assets, T.read_file, T.write_file, T.apply_patch, T.run_shell, T.write_play_manual]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
MAX_TOOL_CALLS_PER_TURN = 16
MANUAL = 'plans/play_manual.json'


def redact(value):
    s = str(value)
    for k, v in os.environ.items():
        key = k.upper()
        credential = (key.endswith(('_KEY', '_TOKEN', '_SECRET', '_PASSWORD')) or key in ('API_KEY', 'TOKEN', 'PASSWORD'))
        if v and len(v) > 5 and credential:
            s = s.replace(v, '[REDACTED]')
    if C.CODER_OPENROUTER_API_KEY:
        s = s.replace(C.CODER_OPENROUTER_API_KEY, '[REDACTED]')
    return s

def _console(e):
    if os.getenv('CODER_VERBOSE', '1') == '0':
        return
    try:
        ev, st = e.get('event'), e.get('step')
        tag = f"[CODER] step {st:>2}" if isinstance(st, int) else "[CODER]        "
        def short(v, n=110):
            v = redact(str(v)).replace('\n', ' ').strip()
            return v if len(v) <= n else v[:n] + '...'
        if ev in ('start', 'resume'):
            line = f"{ev.upper()}  mode={e.get('mode')}  model={e.get('model')}"
        elif ev == 'model':
            u = e.get('usage') or {}
            fin = (e.get('metadata') or {}).get('finish_reason', '')
            line = f"model  in={u.get('input_tokens', '?')} out={u.get('output_tokens', '?')}  {e.get('seconds', '?')}s  {fin}"
        elif ev == 'tool':
            a = e.get('args') or {}
            target = a.get('path') or a.get('paths') or a.get('argv') or a.get('command') or ''
            ok = e.get('outcome') == 'ok'
            line = f"{e.get('tool')}({short(target, 70)}) -> {'OK' if ok else 'ERR ' + short(e.get('result', ''), 100)}"
        elif ev == 'smoke':
            g = e.get('gates') or {}
            line = "checks  " + "  ".join(f"{k}={v}" for k, v in g.items()) + (f"  reason={short(e.get('reason'), 80)}" if e.get('reason') else '')
        elif ev == 'local_failure':
            line = f"local failure ({e.get('source')}): {short(e.get('diagnostics'), 140)}"
        elif ev in ('provider_error', 'provider_retry'):
            line = f"{ev}: {short(e.get('metadata') or e.get('note'), 100)}"
        elif ev == 'end':
            u = e.get('usage') or {}
            line = f"END  status={e.get('status')}  reason={e.get('reason')}  cost=${u.get('known_cost_usd', '?')}"
        elif ev == 'workspace_preparation':
            line = "workspace prepared (old game backed up if present)"
        else:
            return
        print(f"{tag}  {line}", flush=True)
    except Exception:
        pass

def trace(event):
    _console(event)
    def safe(value):
        if isinstance(value, str): return redact(value)
        if isinstance(value, dict): return {k: safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)): return [safe(v) for v in value]
        return value
    ctx = CURRENT.get()
    C.TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with C.TRACE_FILE.open('a', encoding='utf-8') as f:
        f.write(json.dumps(safe(dict(ts=time.time(), attempt_id=ctx.attempt_id if ctx else None, **event)),
                           ensure_ascii=False) + '\n')


def create_model():
    return ChatOpenAI(model=C.AGENT_MODEL, temperature=C.TEMPERATURE, api_key=C.CODER_OPENROUTER_API_KEY,
                      base_url=C.OPENROUTER_BASE_URL, timeout=C.CODER_MODEL_TIMEOUT, max_retries=0, max_tokens=C.CODER_MODEL_MAX_OUTPUT_TOKENS,
                      extra_body={'usage': {'include': True}}).bind_tools(TOOLS)


def _preflight(p):
    if os.name != 'nt':
        raise FileNotFoundError('runtime_unavailable: Windows native sandbox required')
    if p['profile']['renderer'] == 'godot':
        from coder_agent_adhoc.godot_runtime import binary
        if not Path(binary()).is_file():
            raise FileNotFoundError('runtime_unavailable: godot')
    missing = missing_dependencies(p)
    if missing:
        raise FileNotFoundError('runtime_unavailable: ' + ', '.join(missing))


def _record_aborted_attempts():
    """Mark earlier attempts that started but never wrote an end event (killed process)."""
    if not C.TRACE_FILE.is_file():
        return
    started, closed = {}, set()
    for line in C.TRACE_FILE.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('event') == 'start' and e.get('attempt_id'):
            started[e['attempt_id']] = e.get('mode')
        elif e.get('event') == 'end':
            closed.add(e.get('attempt_id'))
        elif e.get('event') == 'aborted':
            closed.add(e.get('aborted_attempt_id'))
    for attempt, mode in started.items():
        if attempt in closed:
            continue
        snapshot = path('traces/repair-' + attempt + '/original')
        trace(dict(event='aborted', aborted_attempt_id=attempt, mode=mode,
                   repair_snapshot=snapshot.relative_to(C.ROOT).as_posix() if snapshot.is_dir() else None,
                   note='no end event; files may hold partial edits' + (', compare with repair_snapshot' if snapshot.is_dir() else '')))


def run_coder(dry_run=False, mode='initial_build', feedback_path=None, resume_attempt_id=None):
    result = dict(status='blocked', mode=mode, renderer=None, entry_point=None, game_dir='game',
                  smoke=dict(plan_and_files='not_run', syntax_or_import='not_run', boot='not_run'), steps=0,
                  play_manual_path=MANUAL, trace_path='traces/coder_attempts.jsonl',
                  approximated_requirements=[], reason=None,
                  debug_statistics=dict(local_failure_events=0, self_debug_attempts=0, external_repair_invocations=0))

    def stop(reason):
        result['reason'] = reason
        return result
    if mode not in ('initial_build', 'repair'):
        return stop('invalid_mode')
    if resume_attempt_id and mode != 'initial_build':
        return stop('resume_only_initial_build')
    feedback = None
    if mode == 'repair':
        from coder_agent_adhoc.repair import validate_feedback
        try:
            feedback = validate_feedback(feedback_path)
        except (ValueError, OSError, TypeError, KeyError) as exc:
            return stop('invalid_feedback: ' + str(exc))
        if feedback['status'] != 'fail' or feedback['failing_stage'] != 'logic_coder':
            return stop('wrong_failing_stage')
    try:
        p = plan(mode=mode)
        current_assets = assets(p)
        result['plan_compatibility_warnings'] = file_contract(p, mode)
        result['runtime_render_settings'] = render_settings(p)
        result['asset_quality_warnings'] = asset_quality_warnings(p, current_assets)
        result['asset_visual_acceptance'] = 'not_run'
        result.update(renderer=p['profile']['renderer'], entry_point=p['architecture']['entry_point'],
                      planner_status=p['status'], unmapped=p['unmapped'],
                      approximated_requirements=[dict(index=i, **r) for i, r in enumerate(p['requirements'])
                                                 if r['status'] == 'approximated'])
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return stop('invalid_plan_or_assets: ' + str(exc))
    allowed_assets = {a['path'] for a in current_assets}
    if dry_run:
        try:
            if resume_attempt_id:
                state = build_state.load(resume_attempt_id)
                result['resume_preview'] = dict(attempt_id=resume_attempt_id, steps_used=state['result'].get('steps', 0),
                                              missing=file_inventory(p)['missing'], usage=state['usage'])
            elif mode == 'initial_build':
                result['workspace_preparation'] = prepare_initial_workspace(dry_run=True, allowed_assets=allowed_assets)
        except (OSError, ValueError) as exc:
            return stop('workspace_preparation_failed: ' + str(exc))
        result['status'] = 'dry_run'
        return result
    if not C.CODER_OPENROUTER_API_KEY:
        return stop('coder_key_missing')
    # Construct the model and check runtime availability before moving the old game.
    try:
        _preflight(p)
        model = create_model()
    except Exception as exc:
        return stop('preflight_or_model_initialization_failed: ' + redact(exc))
    ctx = RunContext(mode, p)
    try:
        with workspace_lock():
            token = CURRENT.set(ctx)
            try:
                # Revalidate inputs under the lock; an external Planner must not race this call.
                if plan(mode=mode) != p or assets(p) != current_assets:
                    raise ValueError('inputs_changed_before_run')
                result['attempt_id'] = ctx.attempt_id
                _record_aborted_attempts()
                state = build_state.load(resume_attempt_id) if resume_attempt_id else None
                return _execute(result, ctx, current_assets, allowed_assets, feedback, feedback_path, model, state)
            finally:
                from coder_agent_adhoc.godot_runtime import release_stage
                try:
                    release_stage()
                finally:
                    CURRENT.reset(token)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return stop('coder_execution_failed: ' + redact(exc))


def _protect_inputs(ctx, feedback, feedback_path):
    """Hash every upstream/test/evidence input; any change aborts the run."""
    for directory in ('plans', 'game/assets', 'game/tests', 'eval_tests'):
        folder = path(directory)
        if folder.is_dir():
            for f in folder.rglob('*'):
                name = f.relative_to(C.ROOT).as_posix()
                if f.is_file() and '__pycache__' not in f.parts and name != MANUAL:
                    ctx.protected[name] = path(name).read_bytes()
    if not feedback:
        return
    for failure in feedback['failures']:
        name = failure['evidence_path']
        ctx.evidence.add(name)
        ctx.protected[name] = path(name).read_bytes()
    ctx.protected[feedback_path] = path(feedback_path).read_bytes()


def _snapshot_repair_originals(ctx, result):
    p = ctx.plan
    for name in [x['path'] for x in p['architecture']['files']] + ['game/project.godot', MANUAL]:
        f = path(name)
        ctx.repair_original[name] = f.read_bytes() if f.is_file() else None
    snapshot = path('traces/repair-' + ctx.attempt_id + '/original')
    for name, data in ctx.repair_original.items():
        if data is not None:
            T.atomic_write(snapshot / name, data)
    result['repair_snapshot_path'] = snapshot.relative_to(C.ROOT).as_posix()


def _rollback_failed_repair(ctx, result):
    restored, conflicts = [], []
    for name, original in ctx.repair_original.items():
        if name not in ctx.written:
            continue
        f = path(name)
        if not f.is_file() or digest(f.read_bytes()) != ctx.write_versions.get(name):
            conflicts.append(name)
            continue
        if original is None:
            f.unlink()
        else:
            T.atomic_write(f, original)
        restored.append(name)
    result['rollback'] = dict(restored_files=restored, conflicts=conflicts)
    if conflicts:
        result['reason'] = 'rollback_conflict_original_in_snapshot: ' + ', '.join(conflicts)


def _execute(result, ctx, current_assets, allowed_assets, feedback, feedback_path, model, resume_state=None):
    p = ctx.plan
    mode = ctx.mode
    ctx.debug_statistics['external_repair_invocations'] = int(mode == 'repair')
    result['debug_statistics'] = ctx.debug_statistics
    if mode == 'initial_build' and not resume_state:
        result['workspace_preparation'] = prepare_initial_workspace(allowed_assets=allowed_assets)
    _protect_inputs(ctx, feedback, feedback_path)
    if feedback:
        _snapshot_repair_originals(ctx, result)
    messages = initial_messages(mode, p, current_assets, feedback, redact)
    usage = dict(model=C.AGENT_MODEL, calls=0, input_tokens=0, output_tokens=0, max_input_tokens_per_call=0,
                 reported_cost_usd=None, known_cost_usd=0.0, cost_missing_calls=0)
    if resume_state:
        messages, usage = build_state.restore(ctx, result, resume_state, messages)
        result['attempt_id'] = ctx.attempt_id
        result['debug_statistics'] = ctx.debug_statistics
        result['workspace_preparation'] = dict(action='resumed_existing_build_no_reset', backup_path=None)
    trace(dict(event='resume' if resume_state else 'start', mode=mode, model=C.AGENT_MODEL, plan_sha256=digest(C.PLAN_FILE.read_bytes()), python=sys.version,
               protected_inputs_sha256={name: digest(data) for name, data in ctx.protected.items()},
               validator_issues=extract_validator_issues(feedback) if feedback else None,
               budgets=dict(steps=C.CODER_MAX_STEPS, seconds=C.CODER_MAX_SECONDS, tokens=C.CODER_MAX_TOKENS,
                            max_output_tokens=C.CODER_MODEL_MAX_OUTPUT_TOKENS,
                            cost_usd=C.CODER_MAX_COST_USD, recent_turns=C.CODER_RECENT_TURNS),
               asset_provenance='upstream_title_renderer_and_asset_validation_only'))
    if mode == 'initial_build':
        trace(dict(event='workspace_preparation', **result['workspace_preparation']))
    result['usage'] = usage
    build_state.save(ctx, result, messages, usage, redact)
    try:
        return _loop(result, ctx, model, messages, usage)
    finally:
        result['changes'] = ctx.changes
        try:
            result['attempted_net_changes'] = net_changes(ctx)
            if mode == 'repair' and result['status'] != 'ready_for_testing':
                _rollback_failed_repair(ctx, result)
            result['net_changes'] = net_changes(ctx)
            result['file_inventory'] = file_inventory(p)
            build_state.save(ctx, result, messages, usage, redact)
            build_state.receipt(result, redact)
            trace(dict(event='end', status=result['status'], reason=result.get('reason'), usage=usage, changes=ctx.changes,
                       net_changes=result['net_changes'], debug_statistics=ctx.debug_statistics,
                       rollback=result.get('rollback')))
        except (OSError, ValueError) as exc:
            result.update(status='blocked', reason='finalization_failed: ' + redact(exc))


def net_changes(ctx):
    """Source/resource delta against the call's start, excluding the manual."""
    originals = ctx.repair_original if ctx.mode == 'repair' else {c['path']: None for c in ctx.changes}
    result = []
    for name, original in sorted(originals.items()):
        if not name.startswith('game/') or name in ctx.protected:
            continue
        f = path(name, game=True)
        after = f.read_bytes() if f.is_file() else None
        if original != after:
            result.append(dict(path=name, before_sha256=digest(original) if original is not None else None,
                               after_sha256=digest(after) if after is not None else None))
    return result


def local_failure(ctx, step, source, reason):
    ctx.debug_statistics['local_failure_events'] += 1
    if ctx.pending_failure_step is None:
        ctx.pending_failure_step = step
    trace(dict(event='local_failure', step=step, source=source, diagnostics=summarize_local_failure(reason)))


def _budget_reason(ctx, usage):
    if ctx.elapsed_before_resume + time.monotonic() - ctx.started >= C.CODER_MAX_SECONDS:
        return 'time_budget_exhausted'
    if usage['input_tokens'] + usage['output_tokens'] >= C.CODER_MAX_TOKENS:
        return 'token_budget_exhausted'
    if C.CODER_MAX_COST_USD is not None:
        if usage['known_cost_usd'] >= C.CODER_MAX_COST_USD:
            return 'cost_budget_exhausted'
        if usage['cost_missing_calls']:
            return 'cost_metadata_unavailable'
    return None


def ensure_model_breakdown(usage):
    if 'by_model' not in usage:
        usage['by_model'] = ({usage['model']: {k: usage.get(k, 0) for k in
            ('calls', 'input_tokens', 'output_tokens', 'known_cost_usd', 'cost_missing_calls')}} if usage.get('calls') else {})


def _record_usage(usage, response):
    tokens = getattr(response, 'usage_metadata', None) or {}
    metadata = getattr(response, 'response_metadata', None) or {}
    input_tokens = tokens.get('input_tokens', 0) or 0
    ensure_model_breakdown(usage)
    current = usage['by_model'].setdefault(C.AGENT_MODEL, dict(calls=0,input_tokens=0,output_tokens=0,known_cost_usd=0.0,cost_missing_calls=0))
    current['calls'] += 1
    current['input_tokens'] += input_tokens
    current['output_tokens'] += tokens.get('output_tokens', 0) or 0
    usage['calls'] += 1
    usage['input_tokens'] += input_tokens
    usage['output_tokens'] += tokens.get('output_tokens', 0) or 0
    usage['max_input_tokens_per_call'] = max(usage['max_input_tokens_per_call'], input_tokens)
    cost = (metadata.get('token_usage') or {}).get('cost')
    if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
        usage['known_cost_usd'] += cost
        current['known_cost_usd'] += cost
    else:
        usage['cost_missing_calls'] += 1
        current['cost_missing_calls'] += 1
    usage['reported_cost_usd'] = usage['known_cost_usd'] if usage['cost_missing_calls'] == 0 else None
    return tokens, metadata


def _run_tool(ctx, step, call):
    """Execute one tool call; returns (ToolMessage content, boot_passed)."""
    start = time.monotonic()
    name = call['name']
    args = call.get('args', {})
    old_count = len(ctx.changes)
    try:
        if name not in TOOLS_BY_NAME:
            raise ValueError('unknown_tool')
        output = redact(TOOLS_BY_NAME[name].invoke(args))
        outcome = 'ok'
    except Exception as exc:
        output = 'ERROR: ' + redact(exc)
        outcome = 'error'
        local_failure(ctx, step, 'tool', output)
    if outcome == 'error':
        ctx.same_tool_failures = ctx.same_tool_failures + 1 if output == ctx.last_tool_error else 1
        ctx.last_tool_error = output
    else:
        ctx.same_tool_failures = 0
    new_changes = ctx.changes[old_count:]
    if (ctx.pending_failure_step is not None and step > ctx.pending_failure_step and
            any(c['before_sha256'] != c['after_sha256'] for c in new_changes)):
        ctx.debug_statistics['self_debug_attempts'] += 1
        ctx.pending_failure_step = None
    summary = {k: (dict(chars=len(v), sha256=digest(v.encode())) if k in ('content', 'old', 'new') and isinstance(v, str) else v)
               for k, v in args.items() if k != 'edits'}
    if 'edits' in args:
        summary['edits'] = len(args['edits'] or [])
    trace(dict(event='tool', step=step, tool=name, args=summary, outcome=outcome, result=output[:C.OUTPUT_LIMIT],
               changes=new_changes, seconds=round(time.monotonic() - start, 3)))
    boot_passed = False
    if name == 'run_shell' and outcome == 'ok':
        try:
            raw = json.loads(output)
            failed = command_failed(raw)
            if failed:
                local_failure(ctx, step, 'run_shell', raw)
            boot_passed = args.get('argv') == ['boot'] and not failed
            output = json.dumps(command_summary(raw), ensure_ascii=False)
        except (ValueError, TypeError, KeyError, AttributeError):
            pass
    return output, boot_passed


def _phase_check(result, ctx, messages, step, force=False):
    """Force an integrated runtime check; model prose cannot skip this phase."""
    from coder_agent_adhoc.presentation import expected
    if ctx.mode != 'initial_build' or not expected(ctx.plan):
        return False
    inventory = file_inventory(ctx.plan)
    if inventory['missing'] or not set(inventory['delivered_promised']) <= ctx.written:
        return False
    fingerprint = digest(json.dumps(build_state.game_hashes(), sort_keys=True).encode())
    if not force and ctx.integration.get('fingerprint') == fingerprint:
        return False
    gates, evidence, reason = integration_smoke(ctx.plan, ctx.protected, ctx.written, ctx.mode, require_manual=False)
    summary = smoke_summary(gates, evidence, reason)
    ctx.integration = dict(fingerprint=fingerprint, step=step, gates=gates, reason=reason,
                           diagnostics=summary, scope='Integration only; full requirement gameplay not established')
    ctx.integration_write_turns = 0
    trace(dict(event='integration_phase', step=step, **{k:v for k,v in ctx.integration.items() if k!='step'}))
    if reason:
        local_failure(ctx, step, 'integration_phase', summary)
    messages.append(HumanMessage(content='Harness integration phase (executed, not a model claim): ' +
        json.dumps(ctx.integration,ensure_ascii=False) +
        ' Fix concrete source/interface errors before expanding or rewriting other files. '
        'Passing this check is NOT full gameplay completion: review and finish every active '
        'requirement before writing the final manual.'))
    result['integration_check'] = ctx.integration
    return bool(reason and 'runtime_unavailable' in reason)


def _loop(result, ctx, model, messages, usage):
    p = ctx.plan
    last_failure = last_progress = None
    repeated = 0

    def budget(reason):
        result.update(status='budget_exhausted', reason=reason)
        return result
    replay_turn = ctx.checkpoint_phase in ('tools', 'turn_complete')
    first_step = result.get('steps', 0) if replay_turn else result.get('steps', 0) + 1
    if ctx.resuming and not replay_turn:
        if _phase_check(result, ctx, messages, result.get('steps',0), force=True):
            result['reason']=ctx.integration['reason']
            return result
    for step in range(max(1, first_step), C.CODER_MAX_STEPS + 1):
        reason = _budget_reason(ctx, usage)
        if reason:
            return budget(reason)
        result['steps'] = step
        started = time.monotonic()
        if replay_turn:
            response = next(m for m in reversed(messages) if isinstance(m, AIMessage))
            replay_turn = False
            metadata = {}
        else:
            update_build_progress(messages, ctx)
            ctx.request_in_flight = True
            build_state.save(ctx, result, messages, usage, redact)
            try:
                response = model.invoke(compact(messages))
            except Exception as exc:
                result['reason'] = 'model_error: ' + redact(exc)
                result['billing_audit_required'] = True
                if exc.__cause__ is not None:
                    result['model_error_cause'] = redact(type(exc.__cause__).__name__ + ': ' + str(exc.__cause__))
                return result
            ctx.request_in_flight = False
            tokens, metadata = _record_usage(usage, response)
            trace(dict(event='model', step=step, usage=tokens, metadata=metadata, seconds=round(time.monotonic() - started, 3)))

        if metadata.get('finish_reason') == 'error' or metadata.get('error'):
            result['reason'] = 'provider_response_error: ' + redact(metadata.get('error') or 'finish_reason=error; no valid completion')
            trace(dict(event='provider_error', step=step, metadata=metadata))
            if (ctx.provider_consecutive < C.CODER_PROVIDER_RETRIES_PER_FAILURE
                    and ctx.provider_retries < C.CODER_PROVIDER_RETRIES_TOTAL
                    and usage['cost_missing_calls'] == 0 and not _budget_reason(ctx, usage)):
                ctx.provider_consecutive += 1
                ctx.provider_retries += 1
                result['provider_error_retries'] = ctx.provider_retries
                trace(dict(event='provider_retry', step=step, note='bounded per-failure and total retry; known billing; inherited budgets'))
                # Failed completions have no valid tool/result exchange to retain.
                # Unknown billing never triggers an automatic retry.
                messages.append(HumanMessage(content='The provider returned an invalid completion; no tool from that '
                    'response was executed. Reissue ONE valid tool call using the exact advertised JSON schema. '
                    'Escape code as a JSON string. For Repair write_file include a concrete reason; if a large '
                    'exact patch is hard to express, re-read and replace the affected file with a reason. '
                    'Keep protected Plan/assets/tests unchanged.'))
                ctx.checkpoint_phase = 'between_turns'
                build_state.save(ctx, result, messages, usage, redact)
                continue
            return result
        ctx.provider_consecutive = 0
        if ctx.checkpoint_phase not in ('tools', 'turn_complete'):
            messages.append(response)
            ctx.pending_calls = [dict(c, _budget_rejected=i >= MAX_TOOL_CALLS_PER_TURN)
                                 for i, c in enumerate(getattr(response, 'tool_calls', []) or [])]
            ctx.checkpoint_phase = 'tools'
            build_state.save(ctx, result, messages, usage, redact)
        if ctx.mode=='initial_build' and (step==1 or (ctx.resuming and not result.get('initial_build_notes'))):
            result['initial_build_notes']=remember_initial_notes(messages,response)
            trace(dict(event='initial_build_notes',notes=result['initial_build_notes'],verified=False))

        calls = getattr(response, 'tool_calls', []) or []
        boot_passed = False
        change_count = len(ctx.changes)
        for call in list(ctx.pending_calls):
            reason = _budget_reason(ctx, usage)
            if reason:
                return budget(reason)
            if call.get('_budget_rejected'):
                output, passed = 'ERROR: per-response tool budget exceeded', False
            else:
                output, passed = _run_tool(ctx, step, call)
            boot_passed = boot_passed or passed
            messages.append(ToolMessage(content=output, tool_call_id=call['id']))
            ctx.pending_calls.pop(0)
            build_state.save(ctx, result, messages, usage, redact)
        ctx.checkpoint_phase = 'turn_complete'
        build_state.save(ctx, result, messages, usage, redact)
        if ctx.same_tool_failures >= C.CODER_REPEATED_TOOL_FAILURE_LIMIT:
            result['reason'] = 'tool_stagnated: ' + ctx.last_tool_error
            return result
        reason = _budget_reason(ctx, usage)
        if reason:
            return budget(reason)

        # Completion candidates: the model stops calling tools, writes the manual, or proves a
        # boot after editing; the last allowed step always gets its final check.
        source_written = any(name.startswith('game/') for name in ctx.written)
        manual_ready = ctx.mode == 'repair' or MANUAL in ctx.written
        candidate = (not calls or any(c['name'] == 'write_play_manual' for c in calls)
                     or (boot_passed and source_written and manual_ready)
                     or (step == C.CODER_MAX_STEPS and source_written))
        if not candidate:
            ctx.checkpoint_phase = 'between_turns'
            if len(ctx.changes) > change_count:
                ctx.integration_write_turns += 1
                if not ctx.integration or ctx.integration_write_turns >= C.CODER_PHASE_CHECK_INTERVAL:
                    if _phase_check(result, ctx, messages, step):
                        result['reason'] = ctx.integration['reason']
                        return result
            missing = file_inventory(p)['missing']
            if source_written and missing:
                messages.append(HumanMessage(content='Build progress: promised files still missing: ' +
                    json.dumps(missing) + '. Complete their integrated implementations; agree class names/preloads, '
                    'signals and method signatures across callers/callees. Do not write the final manual yet.'))
            build_state.save(ctx, result, messages, usage, redact)
            continue
        changed = [name for name, data in ctx.protected.items() if not path(name).is_file() or path(name).read_bytes() != data]
        if changed:
            result['reason'] = 'protected_input_changed: ' + changed[0]
            return result
        if ctx.mode == 'repair' and not net_changes(ctx):
            result['reason'] = 'repair_no_net_changes'
            if step == C.CODER_MAX_STEPS:
                return result
            messages.append(HumanMessage(content='Repair has no final net source/resource changes. A patch followed by its reversal '
                                                 'is not a repair. Read the current source and apply an evidence-based patch.'))
            ctx.checkpoint_phase = 'between_turns'
            continue
        gates, evidence, reason = smoke(p, ctx.protected, ctx.written, ctx.mode)
        result['smoke'] = gates
        result['presentation'] = next((e['presentation'] for e in reversed(evidence) if 'presentation' in e),
                                      dict(status='not_run', reason='no_separate_presentation_probe'))
        trace(dict(event='smoke', step=step, gates=gates, evidence=evidence, reason=reason))
        if not reason:
            result.update(status='ready_for_testing', reason=None)
            claims = _coverage_claims(messages)
            result['coverage_notes'] = redact(claims) if claims else None
            result['requirement_coverage'] = _coverage(p, claims)
            provided = sum(c['coverage_evidence'] != 'not_provided' for c in result['requirement_coverage'])
            result['coverage_status'] = ('not_provided' if not provided else
                                         'provided' if provided == len(p['requirements']) else 'partial')
            return result
        result['reason'] = reason
        local_failure(ctx, step, 'smoke', dict(gates=gates, evidence=evidence, reason=reason))
        if 'runtime_unavailable' in reason:
            return result
        summary = smoke_summary(gates, evidence, reason)
        failure = json.dumps(dict(reason=reason, diagnostics=[r['diagnostics'] for r in summary['commands']]), sort_keys=True)
        names = {x['path'] for x in p['architecture']['files']} | ({'game/project.godot'} if result['renderer'] == 'godot' else set())
        progress = tuple((name, digest(path(name).read_bytes()) if path(name).is_file() else None) for name in sorted(names))
        repeated = repeated + 1 if failure == last_failure and progress == last_progress else 1
        last_failure, last_progress = failure, progress
        if repeated >= C.CODER_STAGNATION_LIMIT:
            result['reason'] = 'stagnated: ' + reason
            return result
        messages.append(HumanMessage(content='Mandatory smoke failed: ' + json.dumps(summary, ensure_ascii=False) +
                                     ' Read the source and fix the failing construct.'))
        ctx.checkpoint_phase = 'between_turns'
        build_state.save(ctx, result, messages, usage, redact)
    return budget('budget_exhausted')


def _coverage_claims(messages):
    """Latest model text that carries a coverage JSON object (it may accompany tool calls)."""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and isinstance(m.content, str) and '"coverage"' in m.content:
            return m.content
    return None


def _coverage(p, content):
    claims = []
    if isinstance(content, str) and '{' in content:
        try:
            raw = json.loads(content[content.index('{'):content.rindex('}') + 1])
            claims = raw.get('coverage', []) if isinstance(raw, dict) else []
        except ValueError:
            claims = []
    if not isinstance(claims, list):
        claims = []
    promised = {x['path'] for x in p['architecture']['files']}
    result = []
    for i, r in enumerate(p['requirements']):
        claim = next((c for c in claims if isinstance(c, dict) and type(c.get('index')) is int and c['index'] == i), {})
        files = claim.get('files', [])
        files = [f for f in files if isinstance(f, str) and f in promised] if isinstance(files, list) else []
        result.append(dict(index=i, planner_status=r['status'], check=r['check'], validator_status='not_run',
                           implementation_files=files, model_claim=claim.get('summary'), limitations=claim.get('limitations', []),
                           coverage_evidence='model_claim_unverified' if files else 'not_provided'))
    return result


if __name__ == '__main__':
    print(json.dumps(run_coder(), ensure_ascii=False, indent=2))
