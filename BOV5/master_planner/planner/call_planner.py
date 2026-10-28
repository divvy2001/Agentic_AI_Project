import importlib.util
import json
import os
import re
import time
from pathlib import Path

import jsonschema
from langchain_openai import ChatOpenAI

from .config.planner_config import (
    OPENROUTER_API_KEY, ASSET_OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    MAX_ATTEMPTS, MODEL, TEMPERATURE, MAX_TOKENS,
    PROMPT_PATH, SCHEMA_PATH, TRACE_FILE, PLAN_FILE, LIBRARIES, GODOT_BINARY,
    PRICE_PER_1M_INPUT, PRICE_PER_1M_OUTPUT, CODER_PLAN_FILE
)

# Load schema and prompt once at startup — not per call
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")


import shutil  # add this import at the top of the file
def probe_environment() -> dict:
    libs = [m for m in LIBRARIES if importlib.util.find_spec(m)]
    godot_path = Path(GODOT_BINARY) if GODOT_BINARY else None
    godot_available = bool(godot_path and godot_path.exists()) or bool(shutil.which("godot"))
    return {
        "libraries": libs,
        "art_generation": bool(ASSET_OPENROUTER_API_KEY),
        "godot": godot_available,
    }


def call_planner(spec: str, probe: dict, prior_error: str | None = None, llm_fn=None, print_prompt: bool = False):
    """
    Build the prompt and call the model once.
    Returns (raw_text, usage_dict) where usage_dict has input_tokens/output_tokens (0 if unavailable).

    - spec: the game spec text
    - probe: output of probe_environment()
    - prior_error: if this is a retry, the validation error from the previous attempt
    - llm_fn: optional fake function for tests — if given, skips the real API call
    """
    system = (PROMPT_TEMPLATE
              .replace("{libs}", ", ".join(probe["libraries"]) or "standard library only")
              .replace("{art_generation}", "available" if probe["art_generation"] else "NOT available")
              .replace("{godot}", "available" if probe["godot"] else "NOT available")
              .replace("{schema}", json.dumps(SCHEMA, indent=1)))

    if print_prompt:
        print("\n" + "=" * 70)
        print("FULL SYSTEM PROMPT SENT TO THE MODEL:")
        print("=" * 70)
        print(system)
        print("=" * 70 + "\n")

    user = f"SPEC:\n<<<\n{spec}\n>>>"


    if prior_error:
        user += f"\n\nYour previous attempt was rejected for these reasons. Fix them:\n{prior_error}"

    if llm_fn:
        return llm_fn(system, user), {"input_tokens": 0, "output_tokens": 0}

    llm = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    response = llm.invoke([("system", system), ("user", user)])
    usage = getattr(response, "usage_metadata", None) or {}
    return response.content, {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


def parse_json(raw: str) -> dict:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)

def _normalize_profile_fields(plan: dict) -> dict:
    """
    The model occasionally writes "reason" instead of the schema's required
    "reasoning" key inside profile fields. Fix it deterministically instead
    of relying on prompt discipline alone — this has recurred across
    multiple fields (players, dimensions), not just the one originally caught.
    """
    profile = plan.get("profile")
    if not isinstance(profile, dict):
        return plan
    for field in profile.values():
        if isinstance(field, dict) and "reason" in field and "reasoning" not in field:
            field["reasoning"] = field.pop("reason")
    return plan

def validate_plan(plan: dict, spec: str, probe: dict) -> list[str]:
    """
    Deterministic validation — no model involved.
    Returns a list of error strings. Empty list means the plan is valid.
    """
    errs = []

    v = jsonschema.Draft7Validator(SCHEMA)
    for e in sorted(v.iter_errors(plan), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in e.path) or "(root)"
        errs.append(f"schema: {path}: {e.message[:200]}")
    if errs:
        return errs

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().casefold()

    spec_n = _norm(spec)

    def check_quote(where, quote):
        if _norm(quote) not in spec_n:
            errs.append(f'quote: {where}: "{quote[:80]}" is not in the spec word for word')

    for key, f in plan["profile"].items():
        src, q = f["source"], f.get("quote")
        if src in ("stated", "inferred"):
            if not q:
                errs.append(f"profile.{key}: source {src} needs a quote")
            else:
                check_quote(f"profile.{key}", q)
        if src == "inferred" and not f.get("reasoning"):
            errs.append(f"profile.{key}: source inferred needs reasoning")
        if src == "assumed":
            if q:
                errs.append(f"profile.{key}: assumed values must not carry a quote")
            if not any(d["about"] == f"profile.{key}" for d in plan["decisions"]):
                errs.append(f'decisions: missing entry with about "profile.{key}" (value is assumed)')

    for i, r in enumerate(plan["requirements"]):
        check_quote(f"requirements[{i}]", r["quote"])
    if not any(r["milestone"] == 1 for r in plan["requirements"]):
        errs.append("requirements: no requirement has milestone 1")

    arch = plan["architecture"]
    paths = [f["path"] for f in arch["files"]]
    if arch["entry_point"] not in paths:
        errs.append(f'architecture.entry_point "{arch["entry_point"]}" is not listed in files')
    if len(set(paths)) != len(paths):
        errs.append("architecture.files: duplicate paths")

    for dep in arch["dependencies"]:
        if dep not in probe["libraries"]:
            errs.append(f'architecture.dependencies: "{dep}" is not installed (installed: {probe["libraries"]})')
    if plan["profile"]["renderer"]["value"] == "pygame" and "pygame" not in arch["dependencies"]:
        errs.append('architecture.dependencies: renderer is pygame but "pygame" is not listed')

    for i, u in enumerate(plan["unmapped"]):
        check_quote(f"unmapped[{i}]", u["quote"])

    return errs


def fallback_plan(spec: str, probe: dict) -> dict:
    first = spec.strip().splitlines()[0] if spec.strip() else "Build a game"
    deps = ["pygame"] if "pygame" in probe["libraries"] else []

    return {
        "game_title": "Untitled Game",
        "profile": {
            "genre":      {"value": "unknown",    "source": "assumed"},
            "renderer":   {"value": "pygame",     "source": "assumed"},
            "dimensions": {"value": "2d",         "source": "assumed"},
            "pace":       {"value": "real-time",  "source": "assumed"},
            "players":    {"value": 1,            "source": "assumed"},
        },
        "requirements": [{
            "text":      "Build the game described in the unmapped spec text",
            "priority":  "core",
            "status":    "approximated",
            "check":     "game window opens and runs for 300 frames without error",
            "milestone": 1,
            "quote":     first,
        }],
        "architecture": {
            "entry_point": "game/main.py",
            "files": [
                {"path": "game/__init__.py", "purpose": "package marker"},
                {"path": "game/main.py",     "purpose": "whole game"},
            ],
            "dependencies": deps,
            "resolution": {"width": 800, "height": 600},
            "fps": 60,
            "assets": {"strategy": "procedural", "sprites": []},
            "requires_input": False,
            "test_input_example": None,
            "extensions": {},
        },
        "decisions": [
            {"about": "profile.genre",      "choice": "unknown",   "reason": "planner failed; default used"},
            {"about": "profile.renderer",   "choice": "pygame",    "reason": "planner failed; default used"},
            {"about": "profile.dimensions", "choice": "2d",        "reason": "planner failed; default used"},
            {"about": "profile.pace",       "choice": "real-time", "reason": "planner failed; default used"},
            {"about": "profile.players",    "choice": "1",         "reason": "planner failed; default used"},
        ],
        "unmapped": [{
            "quote":    spec.strip() if spec.strip() else first,
            "handling": "This is the full spec. Read it and build the game it describes.",
        }],
    }


def _trace_reset():
    """Wipe the trace file at the start of every run."""
    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACE_FILE.write_text("", encoding="utf-8")


def _trace(entry: dict):
    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_FILE.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def _write_plan(plan: dict):
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLAN_FILE.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def _normalize_sprites(plan: dict) -> dict:
    """
    The model sometimes reuses the game's window resolution (e.g. 800x600)
    as a sprite's own width/height — most often for the background — which
    blows past the schema's per-sprite cap (16-512 on each side). Clamp any
    out-of-range dims here, scaling proportionally so art doesn't get
    squashed or stretched. Fixing it deterministically avoids spending a
    retry attempt (and its token cost) on a mistake common enough to just
    handle in code instead of hoping the prompt is followed.
    """
    sprites = (plan.get("architecture") or {}).get("assets", {}).get("sprites")
    if not isinstance(sprites, list):
        return plan

    for sprite in sprites:
        if not isinstance(sprite, dict):
            continue
        w, h = sprite.get("width"), sprite.get("height")
        if not isinstance(w, (int, float)) or not isinstance(h, (int, float)) or w <= 0 or h <= 0:
            continue

        # Scale down proportionally if either side is over the cap.
        scale = min(SPRITE_MAX_DIM / w, SPRITE_MAX_DIM / h, 1.0)
        w, h = w * scale, h * scale

        sprite["width"] = max(SPRITE_MIN_DIM, min(SPRITE_MAX_DIM, round(w)))
        sprite["height"] = max(SPRITE_MIN_DIM, min(SPRITE_MAX_DIM, round(h)))

    return plan

def run_planner(spec: str, llm_fn=None, verbose: bool = True, print_prompt: bool = False) -> dict:
    """
    Main entry point. Calls the model, validates, retries once on failure.
    Prints and traces attempt-by-attempt info: tokens, cost, errors.
    Always writes the final plan to plans/plan.json before returning.
    Returns a valid plan dict. Always. Never raises.
    """

    _trace_reset()

    probe = probe_environment()
    prior_error = None
    last_plan = None
    last_raw = None
    total_input_tokens = 0
    total_output_tokens = 0
    t_start = time.time()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n=== ATTEMPT {attempt} " + "=" * 40)
        t0 = time.time()
        try:
            raw, usage = call_planner(spec, probe, prior_error, llm_fn, print_prompt=(print_prompt and attempt == 1))
        except Exception as e:
            errs = [f"call failed: {type(e).__name__}: {e}"]
            print(f"[ERROR] {errs[0]}")
            _trace({"attempt": attempt, "errors": errs})
            prior_error = "\n".join(errs)
            continue

        last_raw = raw

        in_tok = usage["input_tokens"]
        out_tok = usage["output_tokens"]
        total_input_tokens += in_tok
        total_output_tokens += out_tok
        attempt_cost = (in_tok / 1_000_000 * PRICE_PER_1M_INPUT) + \
                       (out_tok / 1_000_000 * PRICE_PER_1M_OUTPUT)

        if usage["input_tokens"] or usage["output_tokens"]:
            print(f"[TOKENS] in={in_tok} out={out_tok} attempt_cost=${attempt_cost:.5f}")

        try:
            plan = parse_json(raw)
            plan = _normalize_profile_fields(plan)
            plan = _normalize_sprites(plan)
            last_plan = plan
            errs = validate_plan(plan, spec, probe)
        except json.JSONDecodeError as e:
            plan, errs = None, [f"output is not valid JSON: {e}"]

        # "quote:" errors are a soft/eval-style check (did the model copy the
        # spec word-for-word vs. paraphrase it) — they don't reflect a broken
        # plan the way a schema violation or a missing entry_point does. Only
        # hard_errs forces a retry/fallback; quote-only mismatches are logged
        # but the plan is still accepted.
        hard_errs = [e for e in errs if not e.startswith("quote:")]
        quote_errs = [e for e in errs if e.startswith("quote:")]

        if errs:
            print(f"[VALIDATION] {len(errs)} error(s)" + (" (quote-only, non-blocking)" if not hard_errs else "") + ":")
            for err in errs[:5]:
                print(f"  - {err}")
        else:
            print("[VALIDATION] passed")

        _trace({
            "attempt": attempt,
            "seconds": round(time.time() - t0, 1),
            "tokens": {"input": in_tok, "output": out_tok},
            "attempt_cost_usd": round(attempt_cost, 6),
            "errors": errs,
            "hard_errors": hard_errs,
            "quote_errors": quote_errs,
        })

        if not hard_errs:
            plan["status"] = "success"
            if quote_errs:
                plan["quote_warnings"] = quote_errs
            _write_plan(plan)
            _write_coder_plan(plan)   
            total_cost = (total_input_tokens / 1_000_000 * PRICE_PER_1M_INPUT) + \
                         (total_output_tokens / 1_000_000 * PRICE_PER_1M_OUTPUT)
            print(f"\n=== DONE in {attempt} attempt(s), {round(time.time() - t_start, 1)}s ===")
            print(f"[USAGE] input_tokens={total_input_tokens} output_tokens={total_output_tokens} est_cost=${total_cost:.5f}")
            _trace({
                "outcome": "success",
                "attempts": attempt,
                "seconds": round(time.time() - t_start, 1),
                "tokens": {
                    "input": total_input_tokens,
                    "output": total_output_tokens,
                    "total": total_input_tokens + total_output_tokens,
                },
                "estimated_cost_usd": round(total_cost, 5),
            })
            return plan

        # Only feed back hard errors — quote mismatches are accepted, not
        # something the model needs to "fix" on the next attempt.
        prior_error = "\n".join(hard_errs[:10])

    if last_plan is not None:
        plan = last_plan
        plan["status"] = "fallback"
        plan["fallback_reason"] = "validation_failed"   # parsed fine, didn't pass validate_plan
    else:
        plan = fallback_plan(spec, probe)
        plan["raw_model_output"] = last_raw
        plan["status"] = "fallback"
        plan["fallback_reason"] = "unparseable_output"   # never produced valid JSON at all

    assert not validate_plan(fallback_plan(spec, probe), spec, probe), "fallback plan must itself be valid"

    _write_coder_plan(plan)  # keep coder_plan.json in sync even on fallback, so the
                              # Coder never reads a stale plan from an earlier run.

    total_cost = (total_input_tokens / 1_000_000 * PRICE_PER_1M_INPUT) + \
                 (total_output_tokens / 1_000_000 * PRICE_PER_1M_OUTPUT)
    print(f"\n=== FALLBACK after {MAX_ATTEMPTS} attempts, {round(time.time() - t_start, 1)}s ===")
    print(f"[USAGE] input_tokens={total_input_tokens} output_tokens={total_output_tokens} est_cost=${total_cost:.5f}")
    _trace({
        "outcome": "fallback",
        "attempts": MAX_ATTEMPTS,
        "seconds": round(time.time() - t_start, 1),
        "tokens": {
            "input": total_input_tokens,
            "output": total_output_tokens,
            "total": total_input_tokens + total_output_tokens,
        },
        "estimated_cost_usd": round(total_cost, 5),
    })
    _write_plan(plan)
    return plan


def coder_view(plan: dict) -> dict:
    """
    Read-only projection of plan.json for the Coder agent.
    Strips profile's source/quote/reasoning provenance (audit trail for
    humans/Evaluator) down to bare values, and drops `decisions` entirely
    (not addressed to the Coder). Keeps architecture, requirements, and
    unmapped as-is per the schema's own field descriptions.

    Also carries the status field and raw_model_output (when present) —
    the Coder MUST check status before trusting architecture.files.
    """
    view = {
        "status": plan.get("status", "success"),
        "game_title": plan["game_title"],
        "profile": {k: v["value"] for k, v in plan["profile"].items()},
        "requirements": plan["requirements"],
        "architecture": plan["architecture"],
        "unmapped": plan["unmapped"],
    }
    if "raw_model_output" in plan:
        view["raw_model_output"] = plan["raw_model_output"]
    return view

# call_planner.py
def _write_coder_plan(plan: dict):
    CODER_PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    CODER_PLAN_FILE.write_text(json.dumps(coder_view(plan), indent=2), encoding="utf-8")

SPRITE_MIN_DIM, SPRITE_MAX_DIM = 16, 512

