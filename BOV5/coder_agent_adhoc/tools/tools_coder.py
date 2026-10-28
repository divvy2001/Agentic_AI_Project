import difflib, json, os, re, tempfile
from typing import Annotated
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.contracts import path
from coder_agent_adhoc.execution import run_action
from coder_agent_adhoc.run_context import CURRENT, current_plan, digest


def atomic_write(f, content):
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.coder-write-', dir=f.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content); handle.flush(); os.fsync(handle.fileno())
        os.replace(name, f)
    finally:
        if os.path.exists(name): os.unlink(name)


@tool
def read_plan() -> str:
    """Return the immutable Planner coder_plan.json for this run (same as in the first message)."""
    return json.dumps(current_plan(), ensure_ascii=False)


@tool
def read_file(paths: list[str], start_line: int = 0, end_line: int = 0) -> str:
    """Read current UTF-8 text of game/ files, the plan/manifest, or this Repair's evidence.

    paths: up to 16 project-relative paths such as 'game/main.py'.
    start_line/end_line (1-based, inclusive) read a range of ONE file; 0 means whole file.
    Repair and resumed builds must read a file (whole or range) before patching it; the read records the
    current version, so re-read after any external change."""
    ctx = CURRENT.get(); result = []; total = 0
    if len(paths) > 16: raise ValueError('too_many_read_paths')
    ranged = bool(start_line or end_line)
    if ranged and len(paths) != 1: start_line = end_line = 0; ranged = False   # FIX (multi-read): read whole files instead of failing the step
    for name in paths:
        f = path(name)
        allowed = (name.startswith('game/') or name in ('plans/coder_plan.json', 'plans/asset_manifest.json')
                   or (ctx and name in ctx.evidence))
        if not allowed or f.name == '.env' or f.suffix.lower() in ('.env', '.pem', '.key'): raise ValueError('read_denied')
        size = f.stat().st_size; total += size
        if size > 262144 or total > 524288: raise ValueError('read_budget_exceeded')
        data = f.read_bytes(); text = data.decode('utf-8')
        if ctx: ctx.read_versions[name] = digest(data)
        if ranged:
            rows = text.splitlines(True)
            first = max(1, start_line or 1); last = min(len(rows), end_line or len(rows))
            result.append(f'=== {name} (lines {first}-{last} of {len(rows)}) ===\n' + ''.join(rows[first - 1:last]))
        else:
            result.append(f'=== {name} ===\n' + text)
    return '\n'.join(result)


def writable(name):
    f = path(name, game=True); ctx = CURRENT.get()
    if (ctx and name in ctx.protected) or 'tests' in f.relative_to(C.GAME_DIR).parts or f.suffix.lower() in ('.env', '.pem', '.key'):
        raise ValueError('protected_game_file')
    p = current_plan(); promised = {x['path'] for x in p['architecture']['files']}
    if name not in promised and not (p['profile']['renderer'] == 'godot' and name == 'game/project.godot'):
        raise ValueError('file_not_promised_by_planner')
    return f


def commit(name, f, content, kind, reason=''):
    if re.search(r'\[omitted \d+ chars sha256:[^\]]+\]', content):
        raise ValueError('context_summary_is_not_source: read_file for current code and supply complete source or an exact patch')
    if name.endswith(('.gd', '.tscn')) and current_plan()['profile']['renderer']=='godot':
        from coder_agent_adhoc.adapters.godot import resource_contract_problem
        problem=resource_contract_problem(content,current_plan())
        if problem:raise ValueError(problem[0]+': '+problem[1]+' Proposed content rejected; current file unchanged.')
    if name.endswith('.gd') and current_plan()['profile']['renderer']=='godot':   # FIX (godot3 names)
        from coder_agent_adhoc.adapters.godot import godot3_api_problem
        problem=godot3_api_problem(content,name)
        if problem:raise ValueError(problem[0]+': '+problem[1]+' Proposed content rejected; current file unchanged.')
    if name=='game/project.godot' and current_plan()['profile']['renderer']=='godot':
        from coder_agent_adhoc.adapters.godot import project_text_problem
        problem=project_text_problem(content)
        if problem:raise ValueError(problem[0]+': '+problem[1]+' Proposed content rejected; current file unchanged.')
    if name.endswith('.tscn') and current_plan()['profile']['renderer']=='godot':
        from coder_agent_adhoc.adapters.godot import scene_text_problem, scene_uid_problem
        problem=scene_uid_problem(content,name,current_plan())
        if problem:raise ValueError(problem[0]+': '+problem[1]+' Proposed content rejected; current file unchanged.')
        problem=scene_text_problem(content,name)
        if problem:raise ValueError(problem[0]+': '+problem[1]+' Proposed content rejected; current file unchanged.')
    ctx = CURRENT.get(); before = f.read_bytes() if f.is_file() else None
    encoded = content.encode('utf-8')
    if ctx and ctx.resuming and before is not None and before == encoded:
        # An idempotent retry is not a rewrite or a debug improvement. No IO,
        # no new change record, and no relaxation of the Repair net-change gate.
        ctx.written.add(name); ctx.read_versions[name] = digest(encoded)
        ctx.write_versions[name] = digest(encoded)
        return False
    if ctx and (ctx.mode == 'repair' or ctx.resuming) and before is not None:
        if ctx.read_versions.get(name) != digest(before): raise ValueError('repair_read_current_source_required' if ctx.mode == 'repair' else 'resume_read_current_source_required')
        if kind == 'write_file' and not reason.strip(): raise ValueError('repair_full_rewrite_reason_required_prefer_apply_patch' if ctx.mode == 'repair' else 'resume_full_rewrite_reason_required_prefer_apply_patch')
    if len(encoded) > 1048576: raise ValueError('write_budget_exceeded')
    atomic_write(f, encoded)
    if ctx:
        ctx.written.add(name); ctx.read_versions[name] = digest(encoded)
        ctx.write_versions[name] = digest(encoded)
        ctx.changes.append(dict(path=name, tool=kind, reason=reason, before_sha256=digest(before) if before is not None else None,
                                after_sha256=digest(encoded), diff=''.join(difflib.unified_diff(
                                    (before or b'').decode('utf-8').splitlines(True), content.splitlines(True), fromfile=name, tofile=name))))


@tool
def write_file(path: str, content: str, reason: Annotated[str, Field(description='Repair or resumed Build of an existing file REQUIRES a concrete reason for full replacement after read_file. Omit only for a new file in Initial Build.')] = '') -> str:
    """Create or fully replace one Planner-promised file under game/ (or game/project.godot for Godot).

    Use for new files in Initial Build. In Repair or a resumed Build prefer apply_patch; a full rewrite of an
    existing file needs a prior read_file and a concrete reason."""
    f = writable(path); wrote = commit(path, f, content, 'write_file', reason)
    return ('OK: unchanged ' if wrote is False else 'OK: wrote ') + path


class PatchEdit(BaseModel):
    old: str = Field(description='Exact existing text; must occur exactly once at the time it is applied.')
    new: str = Field(description='Replacement text.')


@tool
def apply_patch(path: str, old: str = '', new: str = '', edits: list[PatchEdit] | None = None) -> str:
    """Replace exact text in one existing game/ file; all edits succeed or none are written.

    Give either old/new for one edit, or edits=[{old,new},...] applied in order. Each old must
    be unique in the file at that point; otherwise nothing is written and an error explains
    which edit failed. Existing CRLF line endings are kept. Repair/resume: read_file first."""
    f = writable(path)
    if not f.is_file(): raise ValueError('patch_target_missing_use_write_file')
    pairs = [(e.old, e.new) if isinstance(e, PatchEdit) else (e['old'], e['new']) for e in (edits or [])]
    if old or new: pairs.insert(0, (old, new))
    if not pairs: raise ValueError('patch_requires_old_new_or_edits')
    text = f.read_bytes().decode('utf-8')  # no newline translation
    crlf = '\r\n' in text
    for index, (before, after) in enumerate(pairs):
        if crlf:
            before = before.replace('\r\n', '\n').replace('\n', '\r\n')
            after = after.replace('\r\n', '\n').replace('\n', '\r\n')
        count = text.count(before) if before else 0
        if count != 1:
            anchor=next((line.strip() for line in before.splitlines() if line.strip()),'')
            rows=text.splitlines()
            found=next((i for i,line in enumerate(rows) if anchor and anchor in line),0)
            first=max(0,found-2);last=min(len(rows),found+12)
            excerpt='\n'.join(f'{i+1}: {rows[i]}' for i in range(first,last))[:1600]
            raise ValueError(f'patch_context_not_unique_or_missing: edit {index} matched {count} times; nothing written. '
                             f'Re-read {path} lines {first+1}-{last}; copy exact text, do not guess indentation. Current context:\n'+excerpt)
        text = text.replace(before, after, 1)
    commit(path, f, text, 'apply_patch')
    return f'OK: patched {path} ({len(pairs)} edit(s))'


@tool
def run_shell(argv: list[str]) -> str:
    """Run a fixed sandboxed check: ['syntax'] (compile/import) or ['boot'] (bounded real start).

    No other commands exist. Returns exit code, reason and compact diagnostics with source
    context. Passing is startup evidence only; the harness re-runs all gates before finishing."""
    if len(argv) != 1: raise ValueError('command_not_allowed')
    if argv[0] not in ('syntax','boot'): raise ValueError('command_not_allowed')
    p=current_plan()
    if p['profile']['renderer']=='godot':
        from coder_agent_adhoc.adapters.godot import contract_check,source_check
        problem=contract_check(p) or source_check(p)
        if problem:
            return json.dumps(dict(argv=argv,returncode=1,reason=problem[0],output=problem[1],
                                   phase='source_precheck',seconds=0))
    return json.dumps(run_action(p, argv[0]))


@tool
def write_play_manual(test_input: str, expected_win_output: str, expected_lose_output: str, notes: str) -> str:
    """Write plans/play_manual.json: real controls/inputs, observable WIN/LOSE output, and notes
    (limitations, approximations). Required once per Initial Build; it marks a completion
    candidate but is never evidence that the game works."""
    target = path('plans/play_manual.json')
    atomic_write(target, json.dumps(dict(test_input=test_input, expected_win_output=expected_win_output,
                                         expected_lose_output=expected_lose_output, notes=notes), indent=2).encode('utf-8'))
    ctx = CURRENT.get()
    if ctx:
        ctx.written.add('plans/play_manual.json')
        ctx.write_versions['plans/play_manual.json'] = digest(target.read_bytes())
    return 'OK: manual written'
