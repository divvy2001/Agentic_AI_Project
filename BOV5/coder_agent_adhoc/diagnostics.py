"""Compact deterministic diagnostics for the Coder loop; raw output stays in the trace."""
import re
from coder_agent_adhoc.contracts import path

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
ERROR_LINE = re.compile(r'(SCRIPT ERROR:|Parse Error:|^ERROR:|Traceback|Error:|Exception:)')
GODOT_LOCATION = re.compile(r'res://([A-Za-z0-9_./-]+\.(?:gd|tscn)):(\d+)')
# Sandboxed Python runs on a copy of game/, so map any ".../game/<file>.py" back to game/.
PYTHON_LOCATION = re.compile(r'File "[^"]*?[\\/]game[\\/]([^"]+\.py)", line (\d+)')


def _excerpt(name, number, radius=3):
    rows = path(name, game=True).read_text(encoding='utf-8').splitlines()
    line = int(number)
    return '\n'.join(f'{j + 1}: {rows[j]}' for j in range(max(0, line - radius), min(len(rows), line + radius)))


def source_context(output):
    """Source lines around engine/traceback locations; only game/ files are read."""
    excerpts = {}
    locations = [('game/' + s, n) for s, n in GODOT_LOCATION.findall(output)]
    locations += [('game/' + s.replace('\\', '/'), n) for s, n in PYTHON_LOCATION.findall(output)]
    for name, number in locations:
        key = name + ':' + number
        if key in excerpts or len(excerpts) >= 8:
            continue
        try:
            excerpts[key] = _excerpt(name, number)
        except (OSError, ValueError):
            continue
    return excerpts


def command_summary(result):
    output = ANSI.sub('', result.get('error_check_output', result.get('output', '')))
    lines = output.splitlines()
    errors = []
    for i, line in enumerate(lines):
        if ERROR_LINE.search(line):
            errors.extend(lines[max(0, i - 1):min(len(lines), i + 4)])
    summary = {k: result.get(k) for k in ('returncode', 'reason', 'seconds')}
    summary['diagnostics'] = list(dict.fromkeys(errors))[:50] or lines[-18:]
    summary['nonfatal_engine_diagnostics'] = len(result.get('nonfatal_engine_diagnostics', []))
    if result.get('sandbox'):
        summary['sandbox'] = result['sandbox']
    excerpts = source_context(output)
    if excerpts:
        summary['source_context'] = excerpts
    return summary


def smoke_summary(gates, evidence, reason):
    return dict(gates=gates, reason=reason, commands=[command_summary(r) for r in evidence])


def summarize_local_failure(result):
    """Readable diagnostic adapter only; original tool/smoke logs remain intact."""
    if not isinstance(result, dict):
        return {'reason': str(result)[:4096]}
    if 'gates' in result:
        return smoke_summary(result['gates'], result.get('evidence', []), result.get('reason'))
    return command_summary(result)


def extract_validator_issues(feedback):
    """Trace view of the existing Validator schema, not a new feedback protocol."""
    return dict(suite_version=feedback['suite_version'],
                issues=[{k: failure[k] for k in ('test_id', 'requirement_index', 'expected', 'actual',
                                                 'error_category', 'evidence_path', 'attribution_evidence')}
                        for failure in feedback['failures']],
                previously_passed_test_ids=list(feedback['previously_passed_test_ids']))
