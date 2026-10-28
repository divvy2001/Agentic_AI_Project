"""Durable Initial Build checkpoints; no new Planner/Validator or replay of unknown requests."""
import json
import re
import time
from langchain_core.messages import messages_to_dict, messages_from_dict, HumanMessage, SystemMessage
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.contracts import path
from coder_agent_adhoc.run_context import digest
from coder_agent_adhoc.tools.tools_coder import atomic_write


def game_hashes():
    result = {}
    if C.GAME_DIR.is_dir():
        for f in C.GAME_DIR.rglob('*'):
            name = f.relative_to(C.ROOT).as_posix()
            if any(p in ('.godot', '__pycache__') for p in f.relative_to(C.GAME_DIR).parts):
                continue
            checked = path(name, game=True)
            if checked.is_file():
                result[name] = digest(checked.read_bytes())
    return result


def checkpoint_path(attempt_id):
    if not isinstance(attempt_id, str) or not re.fullmatch(r'[a-f0-9]{32}', attempt_id):
        raise ValueError('invalid_resume_attempt_id')
    return path('traces/build_state/' + attempt_id + '.json')


def save(ctx, result, messages, usage, redact=str):
    if ctx.mode != 'initial_build':
        return
    payload = dict(version=1, attempt_id=ctx.attempt_id, mode=ctx.mode,
        plan_sha256=digest(C.PLAN_FILE.read_bytes()),
        protected_sha256={n: digest(b) for n, b in ctx.protected.items()},
        game_sha256=game_hashes(), written=sorted(ctx.written), changes=ctx.changes,
        result=result, usage=usage, elapsed_seconds=ctx.elapsed_before_resume + time.monotonic() - ctx.started,
        messages=messages_to_dict(messages), phase=ctx.checkpoint_phase,
        pending_calls=ctx.pending_calls, read_versions=ctx.read_versions, request_in_flight=ctx.request_in_flight,
        provider_retries=ctx.provider_retries, integration=ctx.integration,
        integration_write_turns=ctx.integration_write_turns, debug_statistics=ctx.debug_statistics)
    atomic_write(checkpoint_path(ctx.attempt_id), redact(json.dumps(payload, ensure_ascii=False)).encode('utf-8'))


def _legacy(attempt_id):
    """Adopt a pre-checkpoint attempt using its existing start/end/change ledger.

    No old messages are fabricated. Current code is authoritative and the model
    receives an inventory plus the preserved error, then must read before edits.
    """
    rows = []
    if C.TRACE_FILE.is_file():
        for line in C.TRACE_FILE.read_text(encoding='utf-8').splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if item.get('attempt_id') == attempt_id:
                rows.append(item)
    start = next((e for e in rows if e.get('event') == 'start'), None)
    end = next((e for e in reversed(rows) if e.get('event') == 'end'), None)
    if not start or not end or start.get('mode') != 'initial_build':
        raise ValueError('resume_checkpoint_missing_or_legacy_attempt_unclosed')
    if end.get('status') == 'ready_for_testing':
        raise ValueError('resume_already_completed')
    changes = [c for e in rows if e.get('event') == 'tool' for c in e.get('changes', [])]
    latest = {c['path']: c['after_sha256'] for c in changes}
    for name, expected in latest.items():
        if not path(name).is_file() or digest(path(name).read_bytes()) != expected:
            raise ValueError('resume_source_changed: ' + name)
    # An unclassified transport error may have been billed despite absent usage.
    if str(end.get('reason', '')).startswith('model_error:'):
        raise ValueError('resume_billing_audit_required')
    return dict(version=1, legacy=True, attempt_id=attempt_id,
        plan_sha256=start['plan_sha256'], protected_sha256=start.get('protected_inputs_sha256', {}),
        game_sha256=game_hashes(), written=list(latest), changes=changes,
        result=dict(status=end['status'], reason=end.get('reason'),
                    steps=max((e.get('step', 0) or 0 for e in rows), default=0)),
        usage=end['usage'], elapsed_seconds=max(0, end['ts'] - start['ts']),
        phase='between_turns', pending_calls=[], request_in_flight=False,
        provider_retries=sum(e.get('event') == 'provider_retry' for e in rows),
        debug_statistics=end.get('debug_statistics', {}), messages=None)


def load(attempt_id):
    file = checkpoint_path(attempt_id)
    state = json.loads(file.read_text(encoding='utf-8')) if file.is_file() else _legacy(attempt_id)
    if state.get('version') != 1 or state.get('attempt_id') != attempt_id:
        raise ValueError('resume_checkpoint_invalid')
    if state['result']['status'] == 'ready_for_testing':
        raise ValueError('resume_already_completed')
    if state.get('request_in_flight') or state['usage'].get('cost_missing_calls'):
        raise ValueError('resume_billing_audit_required')
    if digest(C.PLAN_FILE.read_bytes()) != state['plan_sha256']:
        raise ValueError('resume_plan_changed')
    for name, expected in state['protected_sha256'].items():
        if not path(name).is_file() or digest(path(name).read_bytes()) != expected:
            raise ValueError('resume_protected_input_changed: ' + name)
    if game_hashes() != state['game_sha256']:
        raise ValueError('resume_source_changed')
    return state


def restore(ctx, result, state, messages):
    ctx.attempt_id = state['attempt_id']
    ctx.written = set(state['written'])
    ctx.changes = state['changes']
    ctx.write_versions = {c['path']: c['after_sha256'] for c in ctx.changes}
    ctx.elapsed_before_resume = state['elapsed_seconds']
    ctx.pending_calls = state.get('pending_calls', [])
    ctx.checkpoint_phase = state.get('phase', 'between_turns')
    ctx.provider_retries = state.get('provider_retries', 0)
    ctx.read_versions = state.get('read_versions', {})
    ctx.resuming = True
    ctx.integration = state.get('integration', {})
    ctx.integration_write_turns = state.get('integration_write_turns', 0)
    ctx.debug_statistics.update(state.get('debug_statistics', {}))
    # Upgrade to the current system guidance, retaining the exact historical
    # exchange and immutable first Plan when available.
    if state.get('messages'):
        restored = messages_from_dict(state['messages'])
        messages = [messages[0], *restored[1:]]
    messages[0] = SystemMessage(content=messages[0].content +
        '\nINITIAL BUILD RESUMPTION OVERRIDE: This phase continues an existing incomplete build, '
        'not the fresh/emptied workspace described above. All prior verified writes count toward '
        'the same build. Do not rewrite completed files merely to mark them fresh, especially '
        'an already-empty game/__init__.py. Read current sources, preserve working code, complete '
        'missing files and patch interface/runtime defects incrementally. Existing-file replacements '
        'require a concrete reason; prefer exact apply_patch. Never invent unplanned scenes.')
    summary = dict(prior_reason=state['result'].get('reason'),
        existing_sources=state['game_sha256'], pending_tools=ctx.pending_calls,
        instructions='Continue the SAME Initial Build. Do not reset the game or replan. '
        'Read current sources before editing existing files; prefer apply_patch, and supply a concrete '
        'reason for full write_file replacements. Repair interfaces and complete missing promised files; '
        'finish real rendering/input/state paths, then run checks. No placeholders.')
    from coder_agent_adhoc.adapters import adapter
    summary['source_precheck'] = adapter(ctx.plan['profile']['renderer']).source_check(ctx.plan)
    # Pending tool exchanges must be completed before inserting a new user turn.
    if not ctx.pending_calls:
        messages.append(HumanMessage(content=json.dumps(dict(resume_initial_build=summary), ensure_ascii=False)))
    result.update(steps=state['result'].get('steps', 0), resumed_from=ctx.attempt_id,
                  resume_count=state['result'].get('resume_count', 0) + 1)
    usage = dict(state['usage'])
    if usage.get('model') != C.AGENT_MODEL:
        result['model_change'] = dict(previous=usage.get('model'), current=C.AGENT_MODEL)
    from coder_agent_adhoc.agent_coder import ensure_model_breakdown
    ensure_model_breakdown(usage)
    usage['model'] = C.AGENT_MODEL
    return messages, usage


def receipt(result, redact=str):
    """The latest outcome is machine-readable even on failure; manual launch uses it."""
    data = {k: v for k, v in result.items() if k not in ('changes', 'attempted_net_changes', 'net_changes')}
    data.update(plan_sha256=digest(C.PLAN_FILE.read_bytes()), game_sha256=game_hashes())
    atomic_write(path('traces/coder_result.json'), redact(json.dumps(data, ensure_ascii=False, indent=2)).encode('utf-8'))
