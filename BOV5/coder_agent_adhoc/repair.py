"""Public incremental Repair entrypoint with fail-closed Validator feedback gating."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from coder_agent_adhoc.configuration.config import GAME_DIR, PLAN_FILE, ROOT

_STAGES = {"planner", "asset", "logic_coder", "runtime_eval_generator", "unknown"}
_CATEGORIES = {"spec", "asset", "behavior", "runtime", "test_definition", "test_infrastructure"}


def _blocked(reason: str) -> dict[str, Any]:
    return {"status": "blocked", "mode": "repair", "reason": reason,
            "renderer": None, "entry_point": None, "game_dir": "game", "steps": 0,
            "smoke": {"plan_and_files":"not_run", "syntax_or_import":"not_run", "boot":"not_run"},
            "play_manual_path":"plans/play_manual.json", "trace_path":"traces/coder_attempts.jsonl",
            "approximated_requirements": [],
            "debug_statistics": {"local_failure_events":0,"self_debug_attempts":0,"external_repair_invocations":0}}


def _file_in_project(path: str) -> Path:
    if not isinstance(path,str) or "\\" in path or ":" in path:
        raise ValueError("invalid_feedback_path")
    raw = Path(path)
    if raw.is_absolute() or not path.strip() or ".." in raw.parts:
        raise ValueError("feedback_path must be project-relative and cannot contain '..'")
    resolved = (ROOT / raw).resolve()
    if not resolved.is_relative_to(ROOT.resolve()):
        raise ValueError("feedback_path points outside the project")
    for parent in [ROOT / raw, *(ROOT / raw).parents]:
        if parent == ROOT.parent: break
        if parent.is_symlink() or (hasattr(parent,"is_junction") and parent.is_junction()):
            raise ValueError("linked_feedback_path_denied")
    if not resolved.is_file():
        raise ValueError("feedback_file_missing")
    return resolved


def _source_exists(path: Any) -> bool:
    try:
        return _file_in_project(path).is_file()
    except ValueError:
        return False


def validate_feedback(feedback_path: str) -> dict[str, Any]:
    """Fail-closed semantic validation of the team's frozen Validator format."""
    p = _file_in_project(feedback_path)
    feedback = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(feedback, dict):
        raise ValueError("feedback_not_an_object")
    if set(feedback) != {"status", "failing_stage", "suite_version", "failures", "previously_passed_test_ids"}:
        raise ValueError("feedback_top_level_fields_invalid")
    status = feedback["status"]
    stage = feedback["failing_stage"]
    if status not in {"pass", "fail", "inconclusive"} or stage not in (_STAGES | {None}):
        raise ValueError("feedback_status_or_stage_invalid")
    if not isinstance(feedback["suite_version"], str) or not feedback["suite_version"].strip():
        raise ValueError("suite_version_missing")
    suite=feedback["suite_version"]
    if not all(c.isalnum() or c in "-_" for c in suite):
        raise ValueError("suite_version_invalid")
    if p != (ROOT / "traces/eval" / suite / "test_results.json").resolve():
        raise ValueError("suite_version_path_mismatch")
    failures = feedback["failures"]
    passes = feedback["previously_passed_test_ids"]
    if not isinstance(failures, list) or not isinstance(passes, list) or not all(isinstance(x, str) for x in passes):
        raise ValueError("feedback_lists_invalid")
    if len(set(passes)) != len(passes):
        raise ValueError("duplicate_passed_test_ids")
    if (status == "fail" and not failures) or (status == "pass" and (stage is not None or failures)) or (status == "inconclusive" and stage != "unknown"):
        raise ValueError("feedback_status_inconsistent")
    if status == "fail" and stage is None:
        raise ValueError("failed_stage_missing")
    if not PLAN_FILE.is_file():
        raise ValueError("coder_plan_missing")
    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    if not isinstance(plan,dict) or not isinstance(plan.get('requirements'),list):
        raise ValueError('invalid_plan_for_feedback')
    count = len(plan.get("requirements", []))
    if not (GAME_DIR.is_dir() and any(x.is_file() for x in GAME_DIR.rglob("*"))):
        raise ValueError("existing_game_missing")
    files=plan.get('architecture',{}).get('files',[]) if isinstance(plan.get('architecture'),dict) else []
    # At least one promised source must exist; Repair may recreate the others.
    if not files or not any(isinstance(x,dict) and _source_exists(x.get('path')) for x in files):
        raise ValueError('existing_game_source_missing')
    required = {"test_id", "requirement_index", "expected", "actual", "error_category", "evidence_path", "attribution_evidence"}
    ids=set()
    for failure in failures:
        if not isinstance(failure, dict) or set(failure) != required:
            raise ValueError("failure_schema_invalid")
        index = failure["requirement_index"]
        if index is not None and (isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < count):
            raise ValueError("requirement_index_out_of_range")
        if failure["error_category"] not in _CATEGORIES:
            raise ValueError("error_category_invalid")
        for k in ("test_id", "expected", "actual", "attribution_evidence"):
            if not isinstance(failure[k], str):
                raise ValueError("failure_field_invalid")
        if not failure["test_id"].strip() or not failure["attribution_evidence"].strip():
            raise ValueError("attribution_evidence_missing")
        if failure["test_id"] in ids or failure["test_id"] in passes:
            raise ValueError("duplicate_or_conflicting_test_id")
        ids.add(failure["test_id"])
        _file_in_project(failure["evidence_path"])
    return feedback


def run_repair(feedback_path: str, dry_run: bool = False, launch_game: bool = True) -> dict[str, Any]:
    """Stable workflow entrypoint. No mutation/model call for invalid/wrong-stage feedback."""
    try:
        feedback = validate_feedback(feedback_path)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        return _blocked(f"invalid_feedback: {exc}")
    if feedback["status"] != "fail" or feedback["failing_stage"] != "logic_coder":
        return _blocked("wrong_failing_stage")
    from coder_agent_adhoc.agent_coder import run_coder
    from coder_agent_adhoc.launch_game import finish_with_play
    return finish_with_play(run_coder(dry_run=dry_run, mode="repair", feedback_path=feedback_path), enabled=launch_game and not dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="PE6203 Coder Repair entrypoint")
    parser.add_argument("--feedback", required=True, help="Project-relative path to Validator test_results.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-launch", action="store_true", help="Do not open a manual play session (automation/eval)")
    args = parser.parse_args()
    outcome = run_repair(args.feedback, dry_run=args.dry_run, launch_game=not args.no_launch)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome["status"] in ("ready_for_testing", "dry_run") and outcome.get('play_session', {}).get('status') != 'failed' else 2


if __name__ == "__main__":
    raise SystemExit(main())
