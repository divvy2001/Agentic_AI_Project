from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass
DEFAULT_MODEL = "openai/gpt-4.1-mini"
ALLOWED_ROUTES = {"asset", "planner", "logic_coder", "unknown"}
ALLOWED_CATEGORIES = {"spec", "asset", "behavior", "runtime", "test_definition", "test_infrastructure"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_project_path(value: str | Path) -> Path:
    p = Path(value)
    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (ROOT / p).resolve()
    if not resolved.is_relative_to(ROOT.resolve()):
        raise ValueError(f"Path must stay inside project root: {value}")
    return resolved


def project_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {project_relative(path)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


def newest_test_results() -> Path:
    # Prefer actual Tester run reports. The suite-root test_results.json is the
    # strict feedback artifact for the existing Logic Coder repair gate.
    candidates = [p for p in (ROOT / "traces" / "eval").glob("*/test_run_*/test_results.json") if p.is_file()]
    if not candidates:
        candidates = [p for p in (ROOT / "traces" / "eval").glob("*/test_results.json") if p.is_file()]
    if not candidates:
        raise FileNotFoundError("No test_results.json found under traces/eval/")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_context_files() -> dict[str, Any]:
    context: dict[str, Any] = {}
    for rel, key in [
        ("plans/plan.json", "planner_plan"),
        ("plans/coder_plan.json", "coder_plan"),
        ("plans/asset_manifest.json", "asset_manifest"),
    ]:
        p = ROOT / rel
        if p.is_file():
            try:
                context[key] = load_json(p, rel)
            except (ValueError, OSError):
                context[key] = {"read_error": f"Could not parse {rel}"}
    return context


def _trim(value: Any, limit: int = 6000) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    return text[:limit] + ("…[truncated]" if len(text) > limit else "")


def _read_evidence(result: dict[str, Any]) -> dict[str, Any]:
    evidence_dir = result.get("evidence_dir")
    if isinstance(evidence_dir, str):
        p = Path(evidence_dir)
        if not p.is_absolute():
            p = ROOT / p
        candidate = (p / "evidence.json").resolve()
        if candidate.is_relative_to(ROOT.resolve()) and candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
    # Some Validator formats put evidence_path on the result itself.
    evidence_path = result.get("evidence_path")
    if isinstance(evidence_path, str):
        try:
            p = safe_project_path(evidence_path)
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {}


def build_diagnostic_context(report: dict[str, Any]) -> dict[str, Any]:
    results = report.get("results", [])
    if not isinstance(results, list):
        results = []
    failing_statuses = {"FAIL", "ERROR", "BLOCKED", "INCONCLUSIVE", "NEEDS_REVIEW"}
    failures = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "")).upper() in failing_statuses:
            evidence = _read_evidence(item)
            failures.append({
                "test_id": item.get("test_id"),
                "status": item.get("status"),
                "requirement_index": item.get("requirement_index"),
                "requirement": item.get("requirement"),
                "assertion": item.get("assertion"),
                "expected": item.get("expected"),
                "actual_reason": item.get("reason"),
                "triage_hints": item.get("triage_hints"),
                "action_results": evidence.get("action_results", item.get("action_results", [])),
                "observations": evidence.get("observations", item.get("observations", [])),
                "runtime_evidence": item.get("runtime_evidence"),
                "evidence_path": item.get("evidence_dir"),
            })
    ctx_files = load_context_files()
    # Give the diagnosis model the actual planner requirements and asset declarations,
    # not the entire repository or unrestricted source tree.
    coder_plan = ctx_files.get("coder_plan", {})
    planner_plan = ctx_files.get("planner_plan", {})
    asset_manifest = ctx_files.get("asset_manifest", {})
    return {
        "run": {
            "suite_version": report.get("suite_version"),
            "game_title": report.get("game_title"),
            "renderer": report.get("renderer"),
            "project_root": str(ROOT),
            "summary": report.get("summary"),
        },
        "failures": failures[:30],
        "requirements": coder_plan.get("requirements", planner_plan.get("requirements", []))[:80]
            if isinstance(coder_plan.get("requirements", planner_plan.get("requirements", [])), list) else [],
        "architecture": coder_plan.get("architecture", planner_plan.get("architecture", {})),
        "profile": coder_plan.get("profile", planner_plan.get("profile", {})),
        "asset_manifest": asset_manifest,
    }


def deterministic_fallback(ctx: dict[str, Any]) -> dict[str, Any]:
    """Conservative fallback when model diagnosis is unavailable."""
    failures = ctx.get("failures", [])
    if not failures:
        return {
            "route": "unknown", "confidence": 0.0,
            "reason": "No failed or inconclusive tests were found.",
            "evidence": [], "repair_instructions": "No action required."
        }
    joined = json.dumps(failures, ensure_ascii=False).lower()
    # Harness/test failures must not be dispatched as game defects.
    if any(x in joined for x in ("unsupported action", "runner error", "requires pyautogui", "no process output captured")):
        return {
            "route": "unknown", "confidence": 0.88,
            "reason": "Evidence points to a tester/adapter or observation gap rather than a confirmed game defect.",
            "evidence": ["At least one failed test includes a harness, unsupported-action, or missing-observation signal."],
            "repair_instructions": "Fix the test adapter or add instrumentation, then rerun the same suite."
        }
    if any(x in joined for x in ("failed to load", "resource not found", "missing asset", "texture", "sprite file", "asset_manifest")):
        return {
            "route": "asset", "confidence": 0.68,
            "reason": "Runtime evidence contains asset/resource-loading signals.",
            "evidence": ["Asset/resource error text or manifest signal was found in the failed-test evidence."],
            "repair_instructions": "Check required assets, paths, file formats, dimensions and manifest validation."
        }
    if any(x in joined for x in ("requirement missing from plan", "not included in plan", "planner omitted")):
        return {
            "route": "planner", "confidence": 0.72,
            "reason": "Evidence explicitly indicates a required feature is absent from the plan.",
            "evidence": ["Failure evidence indicates a requirement-to-plan gap."],
            "repair_instructions": "Re-run Planner using the original game specification and verify every requested requirement is represented."
        }
    if any(x in joined for x in ("traceback", "exception", "null instance", "invalid get index", "collision", "physics", "expected literal text was not found")):
        return {
            "route": "logic_coder", "confidence": 0.55,
            "reason": "Evidence suggests runtime or behavior failure, but the root cause is not proven.",
            "evidence": ["Runtime exception or expected-behavior mismatch appears in the test report."],
            "repair_instructions": "Inspect failing test evidence and make the smallest evidence-based code repair. Verify the original plan and asset manifest first."
        }
    return {
        "route": "unknown", "confidence": 0.25,
        "reason": "Available evidence does not safely distinguish planner, asset, and logic-coder causes.",
        "evidence": ["No sufficiently specific root-cause signal was found."],
        "repair_instructions": "Collect more runtime evidence or review the original brief against the plan, assets and implementation."
    }


def call_openrouter(ctx: dict[str, Any], api_key: str, model: str) -> dict[str, Any]:
    prompt = """You are the Diagnosis/Triage Agent for Bo's Project V4, a game-generation pipeline.
Choose exactly one route:
- planner: original user brief contains a requirement missing or materially misrepresented in the planner output.
- asset: plan is reasonable, but asset generation, manifest, resource paths, file format, or loaded visual resource is the likely root cause.
- logic_coder: plan and required assets are present, but implemented gameplay behavior/code/runtime is wrong.
- unknown: evidence is insufficient, tests are blocked/inconclusive, or the harness itself is failing.

Do not infer root cause from a failed assertion alone. Prefer unknown over a guess. Consider the tester hints as weak evidence only.
Return ONLY JSON with keys:
route (planner|asset|logic_coder|unknown),
confidence (number 0..1),
reason (short string),
evidence (array of specific observations),
repair_instructions (actionable instructions),
failure_categories (object mapping each test_id to one of spec|asset|behavior|runtime|test_definition|test_infrastructure).
Use only evidence in the provided context. Do not claim to have inspected files not included in it.
"""
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 1200,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(ctx, ensure_ascii=False)[:28000]},
        ],
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://openrouter.ai", "X-Title": "Bo V4 Triage Agent"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(content).strip())
    diagnosis = json.loads(content)
    if diagnosis.get("route") not in ALLOWED_ROUTES:
        raise ValueError(f"Model returned unsupported route: {diagnosis.get('route')}")
    confidence = float(diagnosis.get("confidence", 0))
    if not 0 <= confidence <= 1:
        raise ValueError("Model confidence must be between 0 and 1")
    diagnosis["confidence"] = confidence
    diagnosis.setdefault("evidence", [])
    diagnosis.setdefault("failure_categories", {})
    diagnosis.setdefault("repair_instructions", "")
    return diagnosis


def diagnose(ctx: dict[str, Any], model: str, api_key: str | None) -> tuple[dict[str, Any], str]:
    if api_key:
        try:
            return call_openrouter(ctx, api_key, model), "openrouter"
        except Exception as exc:
            fallback = deterministic_fallback(ctx)
            fallback["model_error"] = f"{type(exc).__name__}: {exc}"
            return fallback, "deterministic_fallback"
    return deterministic_fallback(ctx), "deterministic_fallback"


def find_spec_file(explicit: str | None) -> Path | None:
    if explicit:
        p = safe_project_path(explicit)
        if not p.is_file():
            raise FileNotFoundError(f"Spec file not found: {explicit}")
        return p
    candidates = [
        ROOT / "traces" / "original_game_spec.txt",
        ROOT / "plans" / "game_spec.txt",
        ROOT / "game_spec.txt",
        ROOT / "traces" / "game_spec.txt",
    ]
    return next((p for p in candidates if p.is_file()), None)


def dispatch_asset(diagnosis: dict[str, Any]) -> dict[str, Any]:
    plan_path = ROOT / "plans" / "coder_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError("Cannot call Asset Agent: plans/coder_plan.json is missing.")
    from master_planner.run import run_asset_agent
    plan = load_json(plan_path, "coder plan")
    manifest = run_asset_agent(plan)
    if manifest is None:
        return {"status": "not_applicable", "reason": "Planner asset strategy is 'none'; no assets were regenerated."}
    manifest_path = ROOT / "plans" / "asset_manifest.json"
    return {
        "status": "completed",
        "callback": "master_planner.run.run_asset_agent",
        "manifest_path": project_relative(manifest_path),
        "validation": manifest.get("validation"),
        "repair_instructions": diagnosis.get("repair_instructions"),
    }


def dispatch_planner(spec_file: Path | None, diagnosis: dict[str, Any]) -> dict[str, Any]:
    if spec_file is None:
        return {
            "status": "blocked",
            "reason": "Original game specification not found. Re-run triage with --spec-file <project-relative-text-file>.",
            "callback": "master_planner.planner.call_planner.run_planner",
        }
    from master_planner.planner.call_planner import run_planner
    spec = spec_file.read_text(encoding="utf-8")
    plan = run_planner(spec, verbose=True)
    return {
        "status": "completed" if plan.get("status") == "success" else "completed_with_fallback",
        "callback": "master_planner.planner.call_planner.run_planner",
        "spec_file": project_relative(spec_file),
        "planner_status": plan.get("status"),
        "plan_file": "plans/plan.json",
        "coder_plan_file": "plans/coder_plan.json",
        "repair_instructions": diagnosis.get("repair_instructions"),
    }


def _make_logic_feedback(report: dict[str, Any], ctx: dict[str, Any], diagnosis: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    suite_version = str(report.get("suite_version") or "")
    if not suite_version or not all(c.isalnum() or c in "-_" for c in suite_version):
        raise ValueError("test report is missing a safe suite_version")
    plan_path = ROOT / "plans" / "coder_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError("Cannot call Logic Coder repair: plans/coder_plan.json is missing.")
    plan = load_json(plan_path, "coder plan")
    reqs = plan.get("requirements", [])
    req_count = len(reqs) if isinstance(reqs, list) else 0
    results = report.get("results", [])
    failures = []
    passed_ids = []
    categories = diagnosis.get("failure_categories", {}) if isinstance(diagnosis.get("failure_categories"), dict) else {}
    for item in results if isinstance(results, list) else []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).upper()
        tid = str(item.get("test_id") or "")
        if status == "PASS":
            if tid:
                passed_ids.append(tid)
            continue
        if status not in {"FAIL", "ERROR"}:
            continue
        evidence = _read_evidence(item)
        ev_dir = item.get("evidence_dir")
        if not isinstance(ev_dir, str):
            ev_dir = ""
        ev_path = Path(ev_dir)
        if not ev_path.is_absolute():
            ev_path = ROOT / ev_path
        evidence_file = (ev_path / "evidence.json").resolve()
        if not evidence_file.is_file() or not evidence_file.is_relative_to(ROOT.resolve()):
            # Repair gate requires an existing project-local evidence file.
            continue
        idx = item.get("requirement_index")
        if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx < req_count:
            idx = None
        category = categories.get(tid, "behavior")
        if category not in ALLOWED_CATEGORIES:
            category = "behavior"
        actual = item.get("reason") or json.dumps(evidence.get("observations", []), ensure_ascii=False)[:1200] or status
        attribution = diagnosis.get("reason", "Triage routed this failure to Logic Coder.")
        if diagnosis.get("evidence"):
            attribution += " Evidence: " + "; ".join(str(x) for x in diagnosis["evidence"][:5])
        failures.append({
            "test_id": tid or f"unknown-{len(failures)+1}",
            "requirement_index": idx,
            "expected": str(item.get("expected") or ""),
            "actual": str(actual)[:3000],
            "error_category": category,
            "evidence_path": project_relative(evidence_file),
            "attribution_evidence": str(attribution)[:3000],
        })
    if not failures:
        raise ValueError("No actionable FAIL/ERROR cases with project-local evidence were found; Logic Coder repair was not called.")
    feedback = {
        "status": "fail",
        "failing_stage": "logic_coder",
        "suite_version": suite_version,
        "failures": failures,
        "previously_passed_test_ids": passed_ids,
    }
    # Existing coder repair contract requires exactly traces/eval/<suite_version>/test_results.json.
    feedback_path = ROOT / "traces" / "eval" / suite_version / "test_results.json"
    write_json(feedback_path, feedback)
    return feedback_path, feedback


def dispatch_logic_coder(report: dict[str, Any], ctx: dict[str, Any], diagnosis: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    feedback_path, feedback = _make_logic_feedback(report, ctx, diagnosis)
    rel = project_relative(feedback_path)
    if dry_run:
        return {
            "status": "dry_run",
            "callback": "coder_agent_adhoc.repair.run_repair",
            "feedback_path": rel,
            "failure_count": len(feedback["failures"]),
            "note": "Feedback was prepared but the Logic Coder was not invoked.",
        }
    from coder_agent_adhoc.repair import run_repair
    result = run_repair(rel, dry_run=False, launch_game=False)
    return {
        "status": result.get("status", "unknown"),
        "callback": "coder_agent_adhoc.repair.run_repair",
        "feedback_path": rel,
        "failure_count": len(feedback["failures"]),
        "coder_result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bo's Project V4 Diagnosis/Triage Agent.")
    parser.add_argument("--test-results", help="Path to Tester test_results.json; defaults to newest run")
    parser.add_argument("--spec-file", help="Original game specification text file, relative to project root")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenRouter model (default: {DEFAULT_MODEL})")
    parser.add_argument("--api-key", help="OpenRouter key; otherwise uses PLANNER_OPENROUTER_API_KEY or prompts")
    parser.add_argument("--min-confidence", type=float, default=0.65, help="Minimum confidence required for callback (default 0.65)")
    parser.add_argument("--dry-run", action="store_true", help="Diagnose and prepare callback inputs without invoking agents")
    parser.add_argument("--no-llm", action="store_true", help="Use conservative deterministic fallback; no API call")
    parser.add_argument("--report", help="Output report path (default traces/triage/triage_<timestamp>.json")
    args = parser.parse_args()

    try:
        results_path = safe_project_path(args.test_results) if args.test_results else newest_test_results()
        report = load_json(results_path, "Tester results")
    except Exception as exc:
        parser.exit(2, f"triage: cannot load test results: {exc}\n")

    ctx = build_diagnostic_context(report)
    api_key = args.api_key or os.getenv("PLANNER_OPENROUTER_API_KEY")
    has_failures = bool(ctx.get("failures"))
    if has_failures and not api_key and not args.no_llm and not args.dry_run:
        api_key = getpass.getpass("OpenRouter API key for Triage Agent (input hidden): ").strip() or None
    diagnosis, method = diagnose(ctx, args.model, None if args.no_llm or args.dry_run or not has_failures else api_key)

    report_out = {
        "schema_version": "1.0",
        "created_at_utc": utc_now(),
        "input_test_results": project_relative(results_path),
        "diagnosis_method": method,
        "diagnosis": diagnosis,
        "callback": {"status": "not_called"},
        "evidence_summary": {
            "total_tests": len(report.get("results", [])) if isinstance(report.get("results"), list) else 0,
            "failed_tests": len(ctx.get("failures", [])),
        },
    }

    if not ctx.get("failures"):
        report_out["callback"] = {"status": "not_needed", "reason": "No failing/inconclusive tests found."}
    elif diagnosis.get("route") == "unknown":
        report_out["callback"] = {"status": "not_called", "reason": "Diagnosis is unknown; more evidence is required."}
    elif float(diagnosis.get("confidence", 0)) < args.min_confidence:
        report_out["callback"] = {
            "status": "not_called",
            "reason": f"Confidence {diagnosis.get('confidence')} is below threshold {args.min_confidence}.",
        }
    elif args.dry_run:
        if diagnosis["route"] == "logic_coder":
            try:
                report_out["callback"] = dispatch_logic_coder(report, ctx, diagnosis, dry_run=True)
            except Exception as exc:
                report_out["callback"] = {"status": "blocked", "reason": f"{type(exc).__name__}: {exc}"}
        elif diagnosis["route"] == "planner":
            spec_file = find_spec_file(args.spec_file)
            report_out["callback"] = {
                "status": "dry_run",
                "callback": "master_planner.planner.call_planner.run_planner",
                "spec_file": project_relative(spec_file) if spec_file else None,
                "note": "Planner was not invoked in dry-run.",
            }
        else:
            report_out["callback"] = {
                "status": "dry_run",
                "callback": "master_planner.run.run_asset_agent",
                "note": "Asset Agent was not invoked in dry-run.",
            }
    else:
        try:
            route = diagnosis["route"]
            if route == "asset":
                report_out["callback"] = dispatch_asset(diagnosis)
            elif route == "planner":
                report_out["callback"] = dispatch_planner(find_spec_file(args.spec_file), diagnosis)
            elif route == "logic_coder":
                report_out["callback"] = dispatch_logic_coder(report, ctx, diagnosis, dry_run=False)
        except Exception as exc:
            report_out["callback"] = {
                "status": "error",
                "route": diagnosis.get("route"),
                "error": f"{type(exc).__name__}: {exc}",
            }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = safe_project_path(args.report) if args.report else ROOT / "traces" / "triage" / f"triage_{timestamp}.json"
    write_json(output, report_out)
    print(json.dumps(report_out, indent=2, ensure_ascii=False))
    print(f"\nTriage report written: {project_relative(output)}")
    return 0 if report_out["callback"].get("status") not in {"error", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
