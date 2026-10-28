"""Model-visible context: system prompt assembly, first message and history compaction.

The full message history stays in memory and every tool result stays in the trace;
only the view sent to the model is compacted. This is a private transformation, not
a new external protocol.
"""
import json
import re
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.adapters import playbook
from coder_agent_adhoc.contracts import path, render_settings, asset_quality_warnings
from coder_agent_adhoc.run_context import digest

EVIDENCE_EXCERPT = 4000
TEXT_EVIDENCE = ('.log', '.txt', '.json')


def prompt_sections():
    """Parse resources/prompt_coder.txt into its [SECTION] blocks."""
    sections, current = {}, None
    for line in C.PROMPT_FILE.read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'\[([A-Z_]+)\]', line.strip())
        if match:
            current = match[1]; sections[current] = []
        elif current:
            sections[current].append(line)
    return {k: '\n'.join(v).strip() for k, v in sections.items()}


def system_prompt(mode, p):
    s = prompt_sections()
    return '\n\n'.join([s['COMMON'], s['INITIAL_BUILD' if mode == 'initial_build' else 'REPAIR'],
                        s['COMPLETION'], playbook(p)])


def first_message(mode, p, current_assets, feedback=None, redact=str):
    context = dict(mode=mode, plan=p, assets=current_assets)
    context['runtime_render_settings'] = render_settings(p)
    context['asset_quality_warnings'] = asset_quality_warnings(p, current_assets)
    if mode == 'initial_build':
        from coder_agent_adhoc.build_brief import initial_build_brief
        context['implementation_brief'] = initial_build_brief(p)
        context['files_to_write'] = [f['path'] for f in p['architecture']['files']]
        if p['profile']['renderer'] == 'godot' and 'game/project.godot' not in context['files_to_write']:
            context['files_to_write'].append('game/project.godot')
    if feedback:
        failing = {f['requirement_index'] for f in feedback['failures']}
        failures = []
        for failure in feedback['failures']:
            item = dict(failure)
            evidence = path(failure['evidence_path'])
            if evidence.suffix.lower() in TEXT_EVIDENCE:
                text = redact(evidence.read_text(encoding='utf-8', errors='replace'))
                item['evidence_excerpt'] = text[-EVIDENCE_EXCERPT:]
                item['evidence_note'] = (f'last {EVIDENCE_EXCERPT} of {len(text)} chars; read_file the evidence_path for all'
                                         if len(text) > EVIDENCE_EXCERPT else 'complete')
            else:
                item['evidence_note'] = 'non-text evidence; not loaded'
            failures.append(item)
        context['validator_feedback'] = dict(suite_version=feedback['suite_version'], failures=failures)
        # The Validator only lists passed test IDs; requirements without failures must keep working.
        context['regression_guard'] = dict(
            previously_passed_test_ids=feedback['previously_passed_test_ids'],
            requirements_to_preserve=[dict(index=i, text=r['text'], check=r['check'])
                                      for i, r in enumerate(p['requirements']) if i not in failing])
        context['existing_files'] = sorted(
            f.relative_to(C.ROOT).as_posix() for f in C.GAME_DIR.rglob('*')
            if f.is_file() and '.godot' not in f.parts and '__pycache__' not in f.parts)
        context['source_inventory'] = [dict(path=f['path'], bytes=path(f['path']).stat().st_size if path(f['path']).is_file() else None)
                                       for f in p['architecture']['files']]
    return HumanMessage(content=json.dumps(context, ensure_ascii=False))


def initial_messages(mode, p, current_assets, feedback=None, redact=str):
    return [SystemMessage(content=system_prompt(mode, p)), first_message(mode, p, current_assets, feedback, redact)]


def remember_initial_notes(messages, response):
    """Keep the concise first-response implementation contract across compaction.

    This is model-authored advisory data, never a replacement for the Planner.
    No hidden reasoning or generated tool arguments are read here.
    """
    content=getattr(response,'content',None)
    if not isinstance(content,str) or not content.strip() or len(messages)<2:return None
    try:
        context=json.loads(messages[1].content)
    except (ValueError,TypeError):return None
    if context.get('mode')!='initial_build':return None
    note=dict(source='first assistant implementation notes; unverified; immutable Planner takes precedence',
              text=content[:6000],truncated=len(content)>6000)
    context['initial_build_notes']=note
    messages[1]=messages[1].model_copy(update=dict(content=json.dumps(context,ensure_ascii=False)))
    return note


def update_build_progress(messages, ctx):
    """Actual source declarations and check state, not model completion claims."""
    if ctx.mode != 'initial_build' or len(messages) < 2:
        return
    try:
        data = json.loads(messages[1].content)
    except (ValueError, TypeError):
        return
    if not isinstance(data, dict):
        return
    missing = []
    declarations = []
    for item in ctx.plan['architecture']['files']:
        file = path(item['path'], game=True)
        if not file.is_file():
            missing.append(item['path'])
            continue
        if file.suffix not in ('.gd', '.py') or len(declarations) >= 32:
            continue
        text = file.read_text(encoding='utf-8')
        signatures = re.findall(r'^\s*(?:func|(?:async\s+)?def)\s+([^\n]+)', text, re.M)
        declarations.append(dict(path=item['path'], sha256=digest(file.read_bytes()),
            class_names=re.findall(r'^\s*(?:class_name\s+(\w+)|class\s+(\w+))', text, re.M),
            functions=[s[:180] for s in signatures[:12]], functions_truncated=len(signatures)>12,
            signals=re.findall(r'^\s*signal\s+([^\n]+)', text, re.M)[:12],
            exported_names=re.findall(r'^\s*@export\s+var\s+(\w+)', text, re.M)[:16]))
    data['build_progress'] = dict(resuming=ctx.resuming, missing_promised_files=missing,
        verified_prior_writes=sorted(ctx.written), source_declarations=declarations,
        declaration_scope='Names/signatures only; not implementation or gameplay proof',
        integration_check=ctx.integration,
        next_phase='complete_dependency_chain' if missing else
                   'fix_integration_defects' if ctx.integration.get('reason') else
                   'review_all_active_requirements_then_finalize')
    if ctx.resuming:
        data['files_to_write'] = [f['path'] for f in ctx.plan['architecture']['files'] if f['path'] in missing or f['path'] not in ctx.written]
    messages[1] = messages[1].model_copy(update=dict(content=json.dumps(data, ensure_ascii=False)))


def compact(messages, recent_turns=None):
    """Summarize completed old turns as DATA, never as fake executable tool calls.

    Replacing a historical write's content with a placeholder leaves a valid-looking
    write invocation in the model context. Live trials copied that placeholder back
    into source. Keep recent tool/result pairs intact and summarize older pairs in
    one bounded user note, with hashes/lengths instead of replacement source text.
    The original history and the on-disk files are never modified here.
    """
    recent_turns = C.CODER_RECENT_TURNS if recent_turns is None else recent_turns
    turns = [i for i, m in enumerate(messages) if isinstance(m, AIMessage)]
    if len(turns) <= recent_turns:
        return list(messages)
    cutoff = turns[-recent_turns] if recent_turns > 0 else len(messages)
    # Keep the latest read of active source files as bounded, literal DATA. Blindly
    # discarding every read after two turns makes Repair guess exact patch text.
    calls = {}
    latest_reads = {}
    for index, message in enumerate(messages):
        if isinstance(message, AIMessage):
            calls.update({call['id']: call for call in message.tool_calls})
        elif isinstance(message, ToolMessage):
            call = calls.get(message.tool_call_id, {})
            args = call.get('args', {})
            if call.get('name') in ('write_file', 'apply_patch') and str(message.content).startswith('OK:'):
                latest_reads.pop(args.get('path'), None)
            elif call.get('name') == 'read_file' and isinstance(message.content, str):
                markers = list(re.finditer(r'(?m)^=== ([^\n]+?) ===\n', message.content))
                for n, match in enumerate(markers):
                    name = match[1].split(' (lines ', 1)[0]
                    if name.startswith('game/'):
                        end = markers[n+1].start() if n+1 < len(markers) else len(message.content)
                        latest_reads[name] = (index, message.content[match.start():end])
    snapshots = []
    remaining = 8000
    for _, (index, text) in sorted(latest_reads.items(), key=lambda item: item[1][0], reverse=True):
        if index < cutoff and len(text) <= remaining:
            snapshots.append(text);remaining -= len(text)
    history = []
    for m in messages[2:cutoff]:
        if isinstance(m, AIMessage):
            for call in m.tool_calls:
                args = call.get('args', {})
                item = dict(action=call['name'], path=args.get('path'), paths=args.get('paths'), argv=args.get('argv'))
                content = args.get('content')
                if isinstance(content, str):
                    item['requested_content'] = dict(chars=len(content), sha256=digest(content.encode()))
                if 'edits' in args:
                    item['patch_hunks'] = len(args['edits'] or [])
                history.append({k: v for k, v in item.items() if v is not None})
        elif isinstance(m, ToolMessage):
            # Latest full diagnostics/read results remain in the recent turns.
            history.append(dict(result=str(m.content)[:240]))
        elif isinstance(m, HumanMessage):
            history.append(dict(harness_note=str(m.content)[:320]))
    note = HumanMessage(content='COMPLETED HISTORY: non-executable audit summaries, not source code. '
                        'Use read_file for current source; never write a summary or hash into a file. '
                        + json.dumps(history[-16:], ensure_ascii=False)
                        + ('\nLATEST READ SOURCE DATA (invalidated by later successful writes; exact text):\n'
                           + '\n'.join(snapshots) if snapshots else ''))
    first = messages[1]
    if isinstance(first,HumanMessage) and isinstance(first.content,str):
        try:
            context=json.loads(first.content)
            # Provenance quotes duplicate the requirement text/check. Keep every
            # hard field and index, and retain full immutable input via read_plan.
            for requirement in context.get('plan',{}).get('requirements',[]):
                requirement.pop('quote',None)
            first=first.model_copy(update=dict(content=json.dumps(context,ensure_ascii=False)))
        except (ValueError,TypeError,AttributeError):
            pass
    return [messages[0], first, note, *messages[cutoff:]]
