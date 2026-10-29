from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

VALID_RENDERERS = {"terminal", "pygame", "godot"}
VERSION_RE = re.compile(r"^[A-Za-z0-9_-]+$")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON in {label}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return data


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_project_path(project_root: Path, value: str) -> str | None:
    """Return a project-relative POSIX path only if it resolves inside project root."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.replace("\\\\", "/")
    pp = PurePosixPath(raw)
    if pp.is_absolute() or ".." in pp.parts:
        return None
    candidate = (project_root / Path(*pp.parts)).resolve()
    try:
        rel = candidate.relative_to(project_root.resolve())
    except ValueError:
        return None
    if not candidate.is_file() or candidate.is_symlink():
        return None
    return rel.as_posix()


def validate_inputs(plan: dict[str, Any], manual: dict[str, Any], project_root: Path) -> tuple[str, list[dict[str, Any]], list[str]]:
    profile = plan.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    renderer = str(profile.get("renderer", "")).lower()
    if renderer not in VALID_RENDERERS:
        raise ValueError(f"Unsupported or missing plan renderer: {renderer!r}")
    requirements = plan.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Plan must contain a non-empty requirements array")
    for i, req in enumerate(requirements):
        if not isinstance(req, dict) or not (req.get("text") or req.get("check")):
            raise ValueError(f"Requirement {i} must be an object with text or check")
    warnings = []
    if not (project_root / "plans" / "asset_manifest.json").is_file():
        warnings.append("plans/asset_manifest.json is missing; suite generated without asset-manifest evidence")
    if not manual:
        warnings.append("play manual is empty; the model will generate tests from the plan alone")
    return renderer, requirements, warnings


def _manual_inputs(manual: dict[str, Any]) -> dict[str, Any]:
    structured = manual.get("eval")
    return structured if isinstance(structured, dict) else {}


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM response did not contain a JSON object")
        obj = json.loads(text[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError("LLM response must be a JSON object")
    return obj


def _openrouter_generate(plan: dict[str, Any], manual: dict[str, Any], renderer: str,
                         model: str, api_key: str, timeout: int = 90) -> dict[str, Any]:
    """Ask an OpenAI-compatible OpenRouter endpoint to propose test specifications."""
    requirements = plan["requirements"]
    system_prompt = (
        "You are a careful game QA test designer. Return ONLY valid JSON. "
        "Generate executable test specifications, not test results. Never claim a test passed. "
        "SCOPE: CONTROLS ONLY. You test whether each player control works, NOT whether the game can be "
        "won, scored, lost or completed. Work in two steps. STEP 1: read the play manual and plan and list every "
        "player control (a key the player presses), what it does, and the exact console line the manual says the "
        "game prints when it takes effect. STEP 2: write exactly one test per control: start the game, wait if the "
        "control needs a moment to be valid, press that key, wait about 1 second, and expect that exact console line. "
        "Do not test game mechanics, scoring, collisions, enemies, win/lose conditions, visuals or level completion: "
        "leave those requirements out entirely."
    )
    schema = {
        "controls": [{"key": "space", "does": "jump", "prints": "JUMP",
                      "manual_quote": "the exact manual sentence that states this key and its printed line"}],
        "tests": [{
            "test_id": "T01",
            "requirement_index": 0,
            "requirement": "Requirement text",
            "assertion": "Measurable assertion",
            "actions": [{"type": "wait", "seconds": 1}, {"type": "press", "key": "space"}, {"type": "wait", "seconds": 1}],
            "observation": {"method": "stdout", "target": "the console line the play manual says this control prints"},
            "expected": "JUMP",
            "status": "ready_for_validator or not_testable",
            "not_testable_reason": None,
            "timeout_seconds": 30,
            "script_path": None
        }],
        "generation_notes": ["which controls were found, and any control that could not be tested and why"]
    }
    user_payload = {
        "task": "Generate a versioned test suite specification for this game. Return JSON matching the requested shape.",
        "renderer": renderer,
        "game_title": plan.get("game_title", "Untitled game"),
        "plan": plan,
        "play_manual": manual,
        "required_output_shape": schema,
        "constraints": [
            "Fill 'controls' first (STEP 1), then 'tests' (STEP 2). One test per control, test_ids C01, C02, ...",
            "Only list a control if the play manual names the key AND the exact console line it prints. Put the supporting manual sentence in manual_quote. Never invent a printed line.",
            "Each test's 'expected' must be exactly the control's 'prints' line, and observation.method must be stdout.",
            "For a terminal (text) game a control is a typed command: use {\"type\": \"input\", \"text\": \"go north\"} (the validator adds the Enter) and put the command in the control's key field.",
            "Actions: press / key_down / key_up / wait (and input for terminal games) only. Key names are pyautogui names: up, down, left, right, space, enter, esc, and single letters (r, w, a, s, d...). A wait uses 'seconds' (max 30).",
            "If the manual says a control only works in a certain state (e.g. R only after game over, jump only when on the ground), add the inputs/waits needed to reach that state first. If that state cannot be reached reliably with simple inputs, mark the test not_testable and say why.",
            "Set requirement_index to the plan requirement that mentions this control (zero-based); if none fits, use 0.",
            "Do not write code, do not invent script_path values (use null), and do not add tests for anything other than controls."
        ]
    }
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
        ],
        "response_format": {"type": "json_object"}
    }
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://openrouter.ai/",
            "X-Title": "Bo Project V4 Eval Generator"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"OpenRouter API error HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach OpenRouter: {exc.reason}") from exc
    try:
        content = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter response: {str(response_data)[:1000]}") from exc
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenRouter returned an empty message")
    result = _extract_json_object(content)
    if not isinstance(result.get("tests"), list):
        raise ValueError("LLM output must contain a tests array")
    # Keep the exact prompt and raw model output alongside the parsed result, so a
    # grader can see what was actually asked and returned, not only the post-validation
    # suite.json. Popped off by generate_suite() before it's used as test data.
    result["_trace"] = {
        "model": model,
        "system_prompt": system_prompt,
        "user_payload": user_payload,
        "raw_response_content": content,
    }
    return result


def _validate_and_normalize_tests(raw_tests: list[Any], requirements: list[dict[str, Any]],
                                  renderer: str, warnings: list[str]) -> list[dict[str, Any]]:
    """Validate model output; never execute model-generated code."""
    normalized = []
    represented: set[int] = set()
    covered: set[int] = set()
    for i, item in enumerate(raw_tests):
        if not isinstance(item, dict):
            warnings.append(f"LLM test at index {i} was ignored because it was not an object")
            continue
        ri = item.get("requirement_index")
        if not isinstance(ri, int) or isinstance(ri, bool) or ri < 0 or ri >= len(requirements):
            warnings.append(f"LLM test at index {i} has an invalid requirement_index and was ignored")
            continue
        represented.add(ri)
        req = requirements[ri]
        req_text = str(req.get("text") or req.get("check") or "").strip()
        assertion = str(item.get("assertion") or req.get("check") or req_text).strip()
        expected = item.get("expected")
        actions = item.get("actions")
        observation = item.get("observation")
                # --- Hard guardrails: make every test runnable by the real Tester ---
        if isinstance(actions, list):
            fixed = []
            for a in actions:
                if not isinstance(a, dict):
                    fixed.append(a); continue
                a = dict(a)
                if str(a.get("type", "")).lower() == "wait" and "seconds" not in a:
                    if "duration_frames" in a:
                        a["seconds"] = max(1.0, float(a.pop("duration_frames") or 0) / 60)
                    elif "duration" not in a:
                        a["seconds"] = 3
                if "key" not in a and a.get("value") and str(a.get("type", "")).lower() in {"press", "key_down", "key_up"}:
                    a["key"] = str(a["value"]).lower()
                fixed.append(a)
            actions = fixed
        if isinstance(observation, dict):
            method = str(observation.get("method") or "").lower()
            if method in {"game_state", "screen_text", "log"}:
                observation = {**observation, "method": "stdout"}
                if isinstance(item.get("expected"), str) and "[EVENT]" not in item["expected"]:
                    warnings.append(f"Test {item.get('test_id')}: converted {method} to stdout; expected text may not match a printed line")
        status = item.get("status")
        reason = item.get("not_testable_reason")
        valid_ready = (
            isinstance(actions, list) and len(actions) > 0
            and all(isinstance(a, dict) and isinstance(a.get("type"), str) and a.get("type").strip()
                    for a in actions)
            and isinstance(observation, dict) and isinstance(observation.get("method"), str)
            and observation.get("method").strip()
            and isinstance(expected, str) and expected.strip()
        )
        if status == "ready_for_validator" and not valid_ready:
            status = "not_testable"
            reason = "Model-generated test failed structural validation: actions, observation.method, and expected are required."
        elif status not in {"ready_for_validator", "not_testable"}:
            status = "not_testable"
            reason = "Model did not provide a recognized test status."
        if status == "not_testable":
            if not isinstance(actions, list):
                actions = []
            if not isinstance(observation, dict):
                observation = {"method": None}
            if not isinstance(expected, str) or not expected.strip():
                expected = assertion
            if not isinstance(reason, str) or not reason.strip():
                reason = "The model could not define a reliable executable test from the supplied information."
        else:
            covered.add(ri)
            reason = None
        normalized.append({
            "test_id": str(item.get("test_id") or f"T{len(normalized) + 1:02d}"),
            "requirement_index": ri,
            "requirement": req_text,
            "assertion": assertion,
            "actions": actions,
            "observation": observation,
            "expected": expected,
            "status": status,
            "not_testable_reason": reason,
            "renderer": renderer,
            "timeout_seconds": int(item.get("timeout_seconds", 30)) if str(item.get("timeout_seconds", 30)).isdigit() else 30,
            "script_path": None
        })
    for ri, req in enumerate(requirements):
        if ri not in represented:
            req_text = str(req.get("text") or req.get("check") or "").strip()
            normalized.append({
                "test_id": f"T{len(normalized) + 1:02d}",
                "requirement_index": ri,
                "requirement": req_text,
                "assertion": str(req.get("check") or req_text),
                "actions": [],
                "observation": {"method": None},
                "expected": str(req.get("check") or req_text),
                "status": "not_testable",
                "not_testable_reason": "No structurally valid ready_for_validator test covered this requirement.",
                "renderer": renderer,
                "timeout_seconds": 30,
                "script_path": None
            })
            warnings.append(f"Requirement {ri} had no valid executable test and was marked not_testable")
    # Ensure unique IDs, preserving first occurrence.
    seen: set[str] = set()
    for test in normalized:
        base_id = test["test_id"]
        candidate = base_id
        suffix = 2
        while candidate in seen:
            candidate = f"{base_id}_{suffix}"
            suffix += 1
        if candidate != base_id:
            warnings.append(f"Duplicate test_id {base_id!r} renamed to {candidate!r}")
            test["test_id"] = candidate
        seen.add(candidate)
    return normalized


def _enforce_control_scope(tests: list[dict[str, Any]], manual: dict[str, Any], warnings: list[str]) -> list[dict[str, Any]]:
    """Hard guardrail: a ready test must press a key and expect a line the play manual actually mentions."""
    manual_text = json.dumps(manual, ensure_ascii=False).lower()
    kept = []
    for t in tests:
        if t["status"] != "ready_for_validator":
            if t.get("not_testable_reason", "").startswith("No structurally valid"):
                continue  # placeholder for a non-control requirement: out of scope, drop it
            kept.append(t)
            continue
        presses = any(str(a.get("type", "")).lower() in {"press", "key_down", "input"} for a in t["actions"] if isinstance(a, dict))   # input = typed command (terminal games)
        expected = str(t.get("expected") or "").strip()
        if not presses:
            t.update(status="not_testable", not_testable_reason="Out of scope: not a control test (no key press).")
            warnings.append(f"{t['test_id']}: dropped to not_testable, no key press")
        elif not expected or expected.lower() not in manual_text:
            t.update(status="not_testable", not_testable_reason=f"Expected line {expected!r} is not stated in the play manual.")
            warnings.append(f"{t['test_id']}: expected {expected!r} not found in play manual")
        kept.append(t)
    return kept


def generate_suite(project_root: str | Path, suite_version: str = "eval-v1",
                   plan_path: str = "plans/coder_plan.json",
                   manual_path: str = "plans/play_manual.json",
                   backend: str = "openrouter", model: str | None = None,
                   api_key: str | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if not VERSION_RE.fullmatch(suite_version):
        raise ValueError("suite_version may contain only letters, numbers, hyphens and underscores")
    plan_rel = _safe_project_path(root, plan_path)
    manual_rel = _safe_project_path(root, manual_path)
    if not plan_rel:
        raise ValueError(f"Plan must be an existing project-relative file: {plan_path}")
    plan = _read_json(root / plan_rel, "Plan")
    manual: dict[str, Any] = {}
    if manual_rel:
        manual = _read_json(root / manual_rel, "play manual")
    renderer, requirements, warnings = validate_inputs(plan, manual, root)
    if backend not in {"openrouter", "rules"}:
        raise ValueError("backend must be 'openrouter' or 'rules'")
    structured = _manual_inputs(manual)
    generation_notes: list[str] = []
    controls_found: list[dict[str, Any]] = []
    llm_trace: dict[str, Any] | None = None

    if backend == "openrouter":
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            # Prompt interactively instead of requiring a venv or preconfigured environment variable.
            import getpass
            try:
                key = getpass.getpass("Enter your OpenRouter API key (input hidden): ").strip()
            except (EOFError, KeyboardInterrupt):
                raise ValueError("No API key entered; generation cancelled.")
        if not key:
            raise ValueError("No API key entered. Run again and provide your OpenRouter API key.")
        selected_model = model or "openai/gpt-4.1-mini"
        llm_result = _openrouter_generate(plan, manual, renderer, selected_model, key)
        llm_trace = llm_result.pop("_trace", None)
        generation_notes = [str(x) for x in llm_result.get("generation_notes", []) if isinstance(x, str)]
        tests = _validate_and_normalize_tests(llm_result["tests"], requirements, renderer, warnings)
        controls_found = [c for c in llm_result.get("controls", []) if isinstance(c, dict)]
        # FIX (missing controls): every control the model found gets a test, even if it forgot to write one
        tested = {str(a.get("key") or a.get("text") or "").lower() for t in tests for a in t.get("actions", []) if isinstance(a, dict)}
        for c in controls_found:
            key, line = str(c.get("key", "")).lower().strip(), str(c.get("prints", "")).strip()
            if key and line and key not in tested:
                tests.append({"test_id": f"C{len(tests) + 1:02d}", "requirement_index": 0,
                              "requirement": f"Pressing {key} works", "assertion": f"After pressing {key} the game prints {line}",
                              "actions": [{"type": "wait", "seconds": 1},
                                          ({"type": "input", "text": key} if renderer == "terminal" else {"type": "press", "key": key}),
                                          {"type": "wait", "seconds": 1}],
                              "observation": {"method": "stdout", "target": line}, "expected": line,
                              "status": "ready_for_validator", "not_testable_reason": None, "renderer": renderer,
                              "timeout_seconds": 30, "script_path": None})
                warnings.append(f"Added missing control test for {key} -> {line}")
        tests = _enforce_control_scope(tests, manual, warnings)
        generator_info = {"backend": "openrouter", "model": selected_model, "scope": "controls"}
    else:
        # Deterministic mode uses only explicitly supplied structured cases.
        tests = []
        supplied_cases = structured.get("tests", [])
        for i, req in enumerate(requirements):
            match = next((x for x in supplied_cases if isinstance(x, dict) and x.get("requirement_index") == i), None) if isinstance(supplied_cases, list) else None
            req_text = str(req.get("text") or req.get("check") or "").strip()
            check = str(req.get("check") or req_text)
            valid = isinstance(match, dict) and isinstance(match.get("actions"), list) and bool(match["actions"]) and isinstance(match.get("observation"), dict) and bool(match["observation"].get("method")) and isinstance(match.get("expected"), str) and bool(match["expected"].strip())
            tests.append({
                "test_id": str(match.get("test_id") or f"T{i+1:02d}") if match else f"T{i+1:02d}",
                "requirement_index": i, "requirement": req_text, "assertion": check,
                "actions": match["actions"] if valid else [],
                "observation": match["observation"] if valid else {"method": None},
                "expected": match["expected"] if valid else check,
                "status": "ready_for_validator" if valid else "not_testable",
                "not_testable_reason": None if valid else "No explicit structured actions and observable assertion supplied.",
                "renderer": renderer, "timeout_seconds": 30, "script_path": None
            })
        generator_info = {"backend": "rules", "model": None}

    source_hashes = {plan_rel: _sha256(root / plan_rel)}
    if manual_rel:
        source_hashes[manual_rel] = _sha256(root / manual_rel)
    manifest_rel = _safe_project_path(root, "plans/asset_manifest.json")
    if manifest_rel:
        source_hashes[manifest_rel] = _sha256(root / manifest_rel)

    suite = {
        "schema_version": "1.0",
        "suite_version": suite_version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "renderer": renderer,
        "game_title": str(plan.get("game_title") or "Untitled game"),
        "generator": generator_info,
        "generation_notes": generation_notes,
        "controls": controls_found,
        "source_hashes": source_hashes,
        "tests": tests,
        "summary": {
            "total": len(tests),
            "ready_for_validator": sum(t["status"] == "ready_for_validator" for t in tests),
            "not_testable": sum(t["status"] == "not_testable" for t in tests),
        },
        "warnings": warnings + (["No tests are executable until a renderer-specific Validator driver is connected."] if not any(t["status"] == "ready_for_validator" for t in tests) else []),
        "important": "Generation is not execution. This file does not claim PASS and must not be used as test_results.json."
    }

    out_dir = root / "traces" / "eval" / suite_version
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "suite.json"
    if out_file.exists():
        existing = json.loads(out_file.read_text(encoding="utf-8"))
        if existing.get("source_hashes") != source_hashes or existing.get("generator") != generator_info:
            raise FileExistsError(f"Frozen suite {suite_version!r} already exists for different inputs or generator settings. Choose a new suite_version.")
        return existing
    out_file.write_text(json.dumps(suite, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if llm_trace is not None:
        # The exact system/user prompt sent and the raw model response, before any
        # validation or normalization — suite.json only has the post-validation result.
        try:
            (out_dir / "llm_trace.json").write_text(
                json.dumps(llm_trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as exc:
            print(f"[EVAL GENERATOR] llm trace write failed: {type(exc).__name__}: {exc}")
    return suite


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a GenAI-powered, versioned evaluation suite for Bo's Project V4.")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--suite-version", default="eval-v1", help="Letters, numbers, hyphens and underscores only")
    parser.add_argument("--plan", default="plans/coder_plan.json", help="Plan path relative to project root")
    parser.add_argument("--manual", default="plans/play_manual.json", help="Play manual path relative to project root")
    parser.add_argument("--backend", choices=["openrouter", "rules"], default="openrouter", help="openrouter uses GenAI; rules is offline and only uses explicit structured cases")
    parser.add_argument("--model", default=None, help="OpenRouter model ID (optional; defaults to openai/gpt-4.1-mini)")
    args = parser.parse_args()
    try:
        suite = generate_suite(args.project_root, args.suite_version, args.plan, args.manual, args.backend, args.model)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"eval-generator: error: {exc}\n")
    print(json.dumps({
        "suite_version": suite["suite_version"],
        "renderer": suite["renderer"],
        "generator": suite.get("generator"),
        "summary": suite["summary"],
        "controls": [f"{c.get('key')} -> {c.get('prints')}" for c in suite.get("controls", [])],
        "output": f"traces/eval/{suite['suite_version']}/suite.json",
        "warnings": suite["warnings"]
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())