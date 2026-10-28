"""
run_pipeline.py — the full Game Jam Agent loop, as agreed by the team.

    Game spec -> Planner -> Asset Agent -> Logic Coder -> Eval Generator -> Runtime Tester
                                                                              |
                                                       Errors found? -- no --> GAME READY
                                                              | yes
                                                        Triage Agent
                                     routes to: Planner (re-plan + rebuild) | Asset Agent | Coder Repair
                                                              |
                                                     back to Runtime Tester (max MAX_ROUNDS)

It only wires the existing modules together; it does not change any of them.
Run from anywhere:   python run_pipeline.py
Trace of every stage: traces/pipeline/<run_id>/pipeline_trace.jsonl  (+ summary.json)
"""

import csv
import hashlib
import json
import platform
import re
import os
import shutil
import zipfile
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)                      # every module assumes cwd == project root
sys.path.insert(0, str(ROOT))

# ===========================================================================
# SETTINGS: edit these (grouped by pipeline stage)
# ===========================================================================

# --- 1. Game spec (input to the Planner) -----------------------------------
SPEC_DIR = ROOT.parent / "game_specs"   # folder next to BOV5 with one .md file per game
SPEC_FILE = "lantern_cave.md"           # which spec to build; `python run_pipeline.py snake` overrides this for one run
SPEC = ""                              # leave empty: filled with the text under "## Spec" when the run starts

# (Planner model and key live in .env / master_planner; nothing to set here)

# --- 2. Asset Agent --------------------------------------------------------
DRY_RUN_ASSETS = False         # True = plain coloured shapes, no paid AI images (saves ~$0.05/run)

# --- 3. Logic Coder --------------------------------------------------------
# (coder limits live in .env: CODER_MODEL, CODER_MAX_STEPS, CODER_MAX_TOKENS, CODER_MAX_COST_USD ...)

# --- 4. Runtime Tester -----------------------------------------------------
STARTUP_WAIT = 2.0            # seconds to let the game window open before the first key press
TESTER_LIMIT = 0              # run only the first N tests; 0 = run every test in the suite
FAIL_STATUSES = {"FAIL", "ERROR"}   # results that count as "errors found"; BLOCKED / NOT_RUN / NEEDS_REVIEW are reported only

# --- 5. Triage Agent / router (the repair loop) ----------------------------
USE_TRIAGE = True         # False = test once and stop; True = route failures to Planner / Asset / Coder and retest
MAX_ROUNDS = 3                # most test -> triage -> fix cycles before giving up (only when USE_TRIAGE = True)
TRIAGE_MIN_CONFIDENCE = 0.65   # triage only applies a fix when at least this sure, 0..1 (only when USE_TRIAGE = True)

# --- 6. When to stop -------------------------------------------------------
DONE_IF_ANY_PASS = False      # True = finish as soon as one test passes; False = report every result

# --- 7. Outputs ------------------------------------------------------------
TRACK_COST = True             # measure each agent's cost from OpenRouter key usage (free check, ~6 s per stage)
EXPORT_REVIEW = True          # write game/_review (all agent outputs + metrics) and a zip in exports/
COPY_TO_GALLERY = True        # copy each finished game (+ play.bat, GAME_INFO.md, review) to the gallery
GALLERY_DIR = ROOT.parent / "Game that it makes"
RUNS_INDEX = ROOT / "runs_index.csv"   # one row per run (all runs), for comparing runs over time
FINAL_BOOT_SECONDS = 6                 # run the finished game headless this long and save its full output (0 = skip)   # gallery folder; games go into Pygame/, Godot/ or Terminal/

# ===========================================================================
# INTERNAL: filled in while the pipeline runs, do not edit
# ===========================================================================
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")      # this run's id (date_time), used in folder and file names
TRACE_DIR = ROOT / "traces" / "pipeline" / RUN_ID       # this run's trace, stage logs and summary.json
TRACE_DIR.mkdir(parents=True, exist_ok=True)
TRACE_FILE = TRACE_DIR / "pipeline_trace.jsonl"         # one line per stage: turn, time, status
STARTED = time.monotonic()                              # start time, for stage timings
TURN = 0                                                # stage counter ("turn N" in the console)
STATE = {}          # filled during the run; used by the review export (suite path, results path, coder attempt id)
COST = {"coder": 0.0}                                   # coder's self-reported cost (cross-check)
COST_ROWS = []      # {"turn", "round", "agent", "route", "cost_usd"}
ROUTES = []         # triage decisions in order
KEY_NAMES = ["PLANNER_OPENROUTER_API_KEY", "ASSET_OPENROUTER_API_KEY", "CODER_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"]   # .env keys the cost meter checks (each distinct key once)


# ---------------------------------------------------------------------------
# Cost meter: OpenRouter key usage before/after each stage (covers every agent,
# including the modules that do not report their own cost)
# ---------------------------------------------------------------------------
def _distinct_keys():
    env = env_with_keys()
    keys = []
    for name in KEY_NAMES:
        k = (env.get(name) or "").strip().strip('"').strip("'")
        if k and k not in keys:
            keys.append(k)
    return keys


def _usage_once():
    total = 0.0
    for k in _distinct_keys():
        req = urllib.request.Request("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {k}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            total += float(json.loads(r.read().decode()).get("data", {}).get("usage") or 0)
    return total


def usage_now(settle=False):
    """Total spent so far on all project keys. settle=True waits for OpenRouter to finish booking the last calls."""
    if not TRACK_COST:
        return None
    try:
        if not settle:
            return _usage_once()
        last = None
        for _ in range(6):
            time.sleep(3)
            cur = _usage_once()
            if last is not None and abs(cur - last) < 1e-7:
                return cur
            last = cur
        return last
    except Exception as e:
        print(f"[PIPELINE] cost meter unavailable: {e}", flush=True)
        return None


def add_cost(agent, before, after, round_no=None, route=None):
    cost = None if before is None or after is None else max(0.0, after - before)
    COST_ROWS.append({"turn": TURN, "round": round_no, "agent": agent, "route": route,
                      "cost_usd": None if cost is None else round(cost, 5)})
    shown = "n/a" if cost is None else f"${cost:.4f}"
    if not agent.startswith("_"):
        print(f"[COST]     {agent:<28} {shown}", flush=True)
    return cost


def trace(stage, status, **data):
    global TURN
    TURN += 1
    event = {"turn": TURN, "t": round(time.monotonic() - STARTED, 1), "stage": stage, "status": status, **data}
    with TRACE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    extra = "  ".join(f"{k}={v}" for k, v in data.items() if k in ("round", "detail", "route", "confidence", "counts", "cost", "reason"))
    print(f"[PIPELINE] turn {TURN:>2} | {event['t']:>6}s | {stage:<15} | {status:<10} {extra}", flush=True)
    return event


def banner(text):
    print("\n" + "=" * 78 + f"\n  {text}\n" + "=" * 78, flush=True)


def env_with_keys():
    """Pass the project keys to the separate modules so none of them stops to ask for one."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass
    env = dict(os.environ)
    key = env.get("PLANNER_OPENROUTER_API_KEY") or env.get("CODER_OPENROUTER_API_KEY")
    if key and not env.get("OPENROUTER_API_KEY"):
        env["OPENROUTER_API_KEY"] = key           # Eval Generator reads this name
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "eval_generator_module"), env.get("PYTHONPATH", "")])
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_cmd(label, args):
    """Run a module as its own process, stream its output with a prefix, return (code, full_output)."""
    print(f"    $ {' '.join(str(a) for a in args)}", flush=True)
    p = subprocess.Popen([str(a) for a in args], cwd=ROOT, env=env_with_keys(), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    lines = []
    for line in p.stdout:
        lines.append(line)
        print(f"    | {label}: {line.rstrip()}", flush=True)
    p.wait()
    (TRACE_DIR / f"{TURN + 1:02d}_{label}.log").write_text("".join(lines), encoding="utf-8")
    return p.returncode, "".join(lines)


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def stage_plan_and_assets():
    import master_planner.run as mp
    if DRY_RUN_ASSETS:
        os.environ["ASSET_GENERATION_MODE"] = "procedural"
    marks = {"start": usage_now()}
    real_asset_agent = mp.run_asset_agent

    def metered_asset_agent(plan):
        marks["planner_done"] = usage_now(settle=True)
        try:
            return real_asset_agent(plan)
        finally:
            marks["assets_done"] = usage_now(settle=True)

    mp.run_asset_agent = metered_asset_agent      # run() looks the name up at call time
    try:
        plan = mp.run(SPEC, dry_run_planner=False, dry_run_assets=DRY_RUN_ASSETS)
    finally:
        mp.run_asset_agent = real_asset_agent
    add_cost("planner", marks.get("start"), marks.get("planner_done"))
    add_cost("asset_agent", marks.get("planner_done"), marks.get("assets_done"))
    return trace("planner+assets", plan.get("status", "?"),
                 detail=f"renderer={plan['profile']['renderer']['value']} assets={plan['architecture']['assets']['strategy']}",
                 renderer=plan["profile"]["renderer"]["value"], entry_point=plan["architecture"]["entry_point"])


def stage_coder(label="logic_coder", round_no=None, route=None):
    from coder_agent_adhoc.initial_build import run_initial_build
    before = usage_now()
    r = run_initial_build(dry_run=False, launch_game=False)
    cost = (r.get("usage") or {}).get("known_cost_usd") or 0
    COST["coder"] += cost
    STATE.setdefault("coder_attempts", []).append(r.get("attempt_id"))
    STATE["coder_ready"] = r.get("status") == "ready_for_testing"
    add_cost(label, before, usage_now(settle=True), round_no, route)
    return trace("logic_coder", r.get("status"), reason=r.get("reason"), steps=r.get("steps"),
                 cost=f"${cost:.4f}", attempt_id=r.get("attempt_id")), r


def stage_eval(suite_version, round_no=None, route=None):
    before = usage_now()
    code, out = run_cmd("eval", [sys.executable, "-m", "eval_generator.generator",
                                 "--project-root", ".", "--suite-version", suite_version])
    suite = ROOT / "traces" / "eval" / suite_version / "suite.json"
    ok = code == 0 and suite.is_file()
    if ok:
        STATE["suite"] = suite
    n = len(json.loads(suite.read_text(encoding="utf-8")).get("tests", [])) if ok else 0
    add_cost("eval_generator", before, usage_now(settle=True), round_no, route)
    trace("eval_generator", "ok" if ok else "failed", detail=f"suite={suite_version} tests={n}", exit_code=code)
    return suite if ok else None


def launch_command():
    plan = json.loads((ROOT / "plans" / "coder_plan.json").read_text(encoding="utf-8"))
    renderer = plan["profile"]["renderer"] if isinstance(plan["profile"]["renderer"], str) else plan["profile"]["renderer"]["value"]
    entry = plan["architecture"]["entry_point"]

    def q(path):  # quote only if the path has spaces; the tester's Windows split keeps quote chars
        path = str(path)
        return f'"{path}"' if " " in path else path

    if renderer == "godot":
        godot = os.getenv("GODOT_BINARY") or "godot"
        return f'{q(godot)} --path game'
    module = entry[:-3].replace("/", ".") if entry.endswith(".py") else entry
    return f'{q(sys.executable)} -u -m {module}'   # -u: flush prints so the Tester sees them; -m: "from game.x" imports


def godot_import():
    """FIX (godot import): Godot only loads images after its editor has imported them (.godot/imported).
    The coder checks run on a copy, so import the real game/ folder once before testing."""
    plan = json.loads((ROOT / "plans" / "coder_plan.json").read_text(encoding="utf-8"))
    rend = plan["profile"]["renderer"]
    rend = rend if isinstance(rend, str) else rend.get("value")
    if rend != "godot":
        return
    godot = os.getenv("GODOT_BINARY") or "godot"
    try:
        p = subprocess.run([godot, "--headless", "--path", "game", "--import"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        trace("godot_import", "ok" if p.returncode == 0 else f"exit {p.returncode}", detail="imported game/ assets for the Tester")
    except Exception as e:
        trace("godot_import", "failed", reason=f"{type(e).__name__}: {e}")


def stage_tester(suite, round_no):
    godot_import()
    cmd = launch_command()
    args = [sys.executable, ROOT / "bo_v4_tester_v1" / "bo_v4_tester" / "tester.py", "--project-root", ".",
            "--suite", suite.relative_to(ROOT).as_posix(), "--launch-command", cmd,
            "--startup-wait", STARTUP_WAIT]
    if TESTER_LIMIT:
        args += ["--limit", TESTER_LIMIT]
    code, out = run_cmd("tester", args)
    runs = sorted(suite.parent.glob("test_run_*/test_results.json"), key=lambda p: p.stat().st_mtime)
    if not runs:
        trace("runtime_tester", "failed", round=round_no, reason=f"no test_results.json (exit {code})")
        return None, None
    results_path = runs[-1]
    STATE["results"] = results_path
    report = json.loads(results_path.read_text(encoding="utf-8"))
    counts = (report.get("summary") or {}).get("counts", {})
    trace("runtime_tester", "done", round=round_no, counts=counts, results=results_path.relative_to(ROOT).as_posix())
    return results_path, counts


def stage_triage(results_path, round_no):
    before = usage_now()
    out_path = TRACE_DIR / f"triage_round{round_no}.json"
    code, out = run_cmd("triage", [sys.executable, "-m", "triage_agent.triage",
                                   "--test-results", results_path.relative_to(ROOT).as_posix(),
                                   "--spec-file", "traces/original_game_spec.txt",
                                   "--min-confidence", TRIAGE_MIN_CONFIDENCE,
                                   "--report", out_path.relative_to(ROOT).as_posix()])
    if not out_path.is_file():
        trace("triage", "failed", round=round_no, reason=f"no triage report (exit {code})")
        return None
    rep = json.loads(out_path.read_text(encoding="utf-8"))
    d, cb = rep.get("diagnosis", {}), rep.get("callback", {})
    # Triage runs the routed fix itself (planner / asset / coder repair) inside the same process,
    # so split the coder repair out using the coder's own reported cost when available.
    total = add_cost("_triage_total", before, usage_now(settle=True), round_no, d.get("route"))
    COST_ROWS.pop()
    route = d.get("route")
    called = cb.get("status") not in ("not_called", "blocked", "error", "not_needed")
    repair = ((cb.get("coder_result") or {}).get("usage") or {}).get("known_cost_usd") if route == "logic_coder" else None
    if total is None:
        add_cost("triage", None, None, round_no, route)
    elif called and route == "logic_coder" and repair is not None:
        add_cost("triage", 0, max(0.0, total - repair), round_no, route)
        add_cost("coder_repair", 0, repair, round_no, route)
    elif called and route in ("planner", "asset"):
        add_cost(f"triage + {route} fix", 0, total, round_no, route)
    else:
        add_cost("triage", 0, total, round_no, route)
    ROUTES.append({"round": round_no, "route": route, "confidence": d.get("confidence"),
                   "callback": cb.get("status"), "reason": cb.get("reason") or d.get("reason") or ""})
    trace("triage", cb.get("status", "?"), round=round_no, route=d.get("route"),
          confidence=d.get("confidence"), reason=cb.get("reason") or d.get("summary") or "")
    return rep


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def print_cost_report(by_agent, total):
    print("\nCOST BY STAGE")
    print(f"  {'turn':<5} {'round':<6} {'agent':<28} {'route':<12} cost")
    for r in COST_ROWS:
        c = "n/a" if r["cost_usd"] is None else f"${r['cost_usd']:.4f}"
        print(f"  {r['turn']:<5} {str(r['round'] or '-'):<6} {r['agent']:<28} {str(r['route'] or '-'):<12} {c}")
    print("\nCOST BY AGENT")
    for a, c in by_agent.items():
        print(f"  {a:<28} ${c:.4f}")
    print(f"  {'TOTAL':<28} ${total:.4f}" if total is not None else "  TOTAL                        n/a")
    if ROUTES:
        print("\nROUTING")
        for r in ROUTES:
            print(f"  round {r['round']}: triage -> {r['route']}  (confidence {r['confidence']}, callback {r['callback']})  {r['reason'][:90]}")
    else:
        print("\nROUTING\n  none (triage not needed)")



# ---------------------------------------------------------------------------
# Review export: game/_review/ (+ exports/<run>.zip with game + review)
# ---------------------------------------------------------------------------
def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _jsonl(path):
    try:
        return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def _copy(src, dst):
    src, dst = Path(src), Path(dst)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build_metrics(summary):
    """One table of numbers per agent: status, time, tokens, cost, and agent-specific counts."""
    trace_rows = _jsonl(TRACE_FILE)
    t = {e["stage"]: e for e in trace_rows}
    prev, secs = 0.0, {}
    for e in trace_rows:                       # stage duration = time since previous trace event
        secs[e["stage"]] = round(e["t"] - prev, 1); prev = e["t"]
    cost = summary.get("cost_by_agent", {})
    plan = _read_json(ROOT / "plans" / "plan.json") or _read_json(ROOT / "plans" / "coder_plan.json") or {}
    rend = (plan.get("profile") or {}).get("renderer")
    rend = rend.get("value") if isinstance(rend, dict) else rend
    planner_att = _jsonl(ROOT / "traces" / "planner_attempts.jsonl")
    manifest = _read_json(ROOT / "plans" / "asset_manifest.json") or {}
    coder = _read_json(ROOT / "traces" / "coder_result.json") or {}
    cu = coder.get("usage") or {}
    suite = _read_json(STATE["suite"]) if STATE.get("suite") else {}
    results = _read_json(STATE["results"]) if STATE.get("results") else {}
    res = (results or {}).get("results", [])
    reqs = plan.get("requirements", [])
    assets = manifest.get("assets", [])
    return {
        "run_id": RUN_ID, "outcome": summary.get("outcome"), "total_seconds": summary.get("elapsed_s"),
        "total_cost_usd": summary.get("total_cost_usd"),
        "planner": {
            "status": plan.get("status"), "attempts": len(planner_att),
            "seconds": secs.get("planner+assets"),
            "tokens_in": sum((a.get("tokens") or {}).get("input", 0) for a in planner_att),
            "tokens_out": sum((a.get("tokens") or {}).get("output", 0) for a in planner_att),
            "cost_usd": cost.get("planner"),
            "renderer": rend, "game_title": plan.get("game_title"),
            "requirements": len(reqs),
            "requirements_by_status": {k: sum(1 for r in reqs if r.get("status") == k) for k in {r.get("status") for r in reqs}},
            "hard_errors_seen": sum(len(a.get("hard_errors") or []) for a in planner_att),
            "quote_warnings_seen": sum(len(a.get("quote_errors") or []) for a in planner_att),
        },
        "asset_agent": {
            "strategy": ((plan.get("architecture") or {}).get("assets") or {}).get("strategy"),
            "assets": len(assets), "cost_usd": cost.get("asset_agent"),
            "files": [a.get("path") for a in assets if isinstance(a, dict)],
        },
        "logic_coder": {
            "status": coder.get("status"), "reason": coder.get("reason"),
            "steps": t.get("logic_coder", {}).get("steps"), "seconds": secs.get("logic_coder"),
            "model": cu.get("model"), "calls": cu.get("calls"),
            "tokens_in": cu.get("input_tokens"), "tokens_out": cu.get("output_tokens"),
            "cost_usd_metered": cost.get("logic_coder"), "cost_usd_self_reported": cu.get("known_cost_usd"),
            "files_written": sorted({c.get("path") for c in coder.get("changes", []) if isinstance(c, dict)}),
        },
        "eval_generator": {
            "status": t.get("eval_generator", {}).get("status"), "seconds": secs.get("eval_generator"),
            "cost_usd": cost.get("eval_generator"), "model": ((suite or {}).get("generator") or {}).get("model"),
            "controls_found": [f"{c.get('key')} -> {c.get('prints')}" for c in (suite or {}).get("controls", [])],
            "tests": ((suite or {}).get("summary") or {}),
        },
        "runtime_tester": {
            "seconds": secs.get("runtime_tester"), "counts": ((results or {}).get("summary") or {}).get("counts"),
            "tests": [{"id": x.get("test_id"), "expected": x.get("expected"), "status": x.get("status"),
                       "retries": x.get("input_retries", 0),
                       "window_focused": [a.get("window_focused") for a in x.get("action_results", []) if "window_focused" in a],
                       "seconds": x.get("duration_seconds")} for x in res],
        },
        "triage_router": {"enabled": USE_TRIAGE, "decisions": summary.get("routing", [])},
    }


def review_markdown(m):
    L = [f"# Run review: {m['run_id']}", "", f"**Outcome:** {m['outcome']}  ",
         f"**Total time:** {m['total_seconds']} s  ", f"**Total cost:** ${m['total_cost_usd']}", "",
         "## Spec", "", "```", SPEC, "```", "",
         "## Agents", "", "| Agent | Status | Time (s) | Tokens in/out | Cost ($) | Notes |", "|---|---|---|---|---|---|"]
    p, a, c, e, t = m["planner"], m["asset_agent"], m["logic_coder"], m["eval_generator"], m["runtime_tester"]
    L.append(f"| Planner | {p['status']} | {p['seconds']} (incl. assets) | {p['tokens_in']}/{p['tokens_out']} | {p['cost_usd']} | {p['attempts']} attempt(s), {p['requirements']} requirements, renderer {p['renderer']} |")
    L.append(f"| Asset Agent | {a['strategy']} | – | – | {a['cost_usd']} | {a['assets']} asset(s) |")
    L.append(f"| Logic Coder | {c['status']} | {c['seconds']} | {c['tokens_in']}/{c['tokens_out']} | {c['cost_usd_metered']} (self-reported {c['cost_usd_self_reported']}) | {c['steps']} steps, {c['calls']} calls, {c['model']} |")
    L.append(f"| Eval Generator | {e['status']} | {e['seconds']} | – | {e['cost_usd']} | {len(e['controls_found'])} controls found |")
    L.append(f"| Runtime Tester | done | {t['seconds']} | – | 0 | {t['counts']} |")
    L.append(f"| Triage / Router | {'on' if m['triage_router']['enabled'] else 'off'} | – | – | – | {len(m['triage_router']['decisions'])} decision(s) |")
    L += ["", "## Control tests", "", "| Test | Expected line | Result | Retries | Window focused |", "|---|---|---|---|---|"]
    for x in t["tests"]:
        L.append(f"| {x['id']} | `{x['expected']}` | {x['status']} | {x['retries']} | {x['window_focused']} |")
    L += ["", "## Files in this folder", "",
          "- `DEBUG_TURNS.md`: every pipeline stage, every coder step (model call, tools, checks), every Tester action, and a loop analysis",
          "- `metrics.json`: all numbers above, per agent (+ loop_analysis)",
          "- `settings.json`: models, limits, tool versions and prompt/agent file versions used for this run (no keys)",
          "- `CHECK_OUTPUT.md`: complete engine output of every coder syntax/boot check",
          "- `FINAL_BOOT.md`: complete output of the finished game run headless for a few seconds",
          "- `HUMAN_CHECK.md`: fill in after playing; the ground truth to compare with the Tester",
          "- `1_planner/`: spec, plan.json, coder_plan.json, planner_attempts.jsonl",
          "- `2_assets/`: asset_manifest.json",
          "- `3_coder/`: coder_result.json, coder_trace.jsonl (this run's steps only), play_manual.json",
          "- `4_eval/`: suite.json (controls + tests)",
          "- `5_tester/`: test_results.json + evidence/ (stdout/stderr per test)",
          "- `6_pipeline/`: pipeline_trace.jsonl, summary.json, stage logs, triage reports"]
    return "\n".join(L) + "\n"



def _short(v, n=220):
    t = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    t = " ".join(t.split())
    return t if len(t) <= n else t[:n] + "..."


def _err_code(text):
    m = re.search(r"ERROR:\s*([A-Za-z0-9_]+)", str(text))
    return m.group(1) if m else (str(text).split(":")[0][:40] or "error")


def build_turn_log(summary):
    """DEBUG_TURNS.md: every pipeline stage + every coder step (model call, tools, checks) + every
    Tester action, followed by a loop analysis (where steps were wasted and on what)."""
    import collections
    pipe = _jsonl(TRACE_FILE)
    ids = set(STATE.get("coder_attempts", []))
    rows = [r for r in _jsonl(ROOT / "traces" / "coder_attempts.jsonl") if r.get("attempt_id") in ids]
    results = _read_json(STATE["results"]) if STATE.get("results") else {}
    L = [f"# Turn-by-turn debug log: {RUN_ID}", "",
         f"Spec: `{Path(STATE.get('spec_file', '')).name}`  ", f"Outcome: **{summary.get('outcome')}**  ",
         f"Total: {summary.get('elapsed_s')} s, ${summary.get('total_cost_usd')}", "",
         "## 1. Pipeline stages", "", "| Turn | Time (s) | Stage | Status | Detail |", "|---|---|---|---|---|"]
    for e in pipe:
        det = e.get("detail") or e.get("reason") or e.get("counts") or ""
        L.append(f"| {e.get('turn')} | {e.get('t')} | {e.get('stage')} | {e.get('status')} | {_short(det, 140)} |")

    # ---- coder steps
    steps = collections.OrderedDict()
    for r in rows:
        k = int(r["step"]) if str(r.get("step", "")).isdigit() else 0
        steps.setdefault(k, []).append(r)
    L += ["", "## 2. Coder steps", ""]
    errors, tools, files_written, reads = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    first_pass, gate_history, last_err, repeats = {}, [], None, 0
    tok_in = tok_out = 0
    for k, evs in steps.items():
        if k == 0:
            for r in evs:
                if r.get("event") == "start":
                    L.append(f"- **start**: model `{r.get('model')}`, budgets {_short(r.get('budgets'), 200)}")
                elif r.get("event") == "workspace_preparation":
                    L.append(f"- **workspace**: {r.get('action')} (backup: {r.get('backup_path')})")
                elif r.get("event") == "end":
                    u = r.get("usage") or {}
                    L.append(f"- **end**: status `{r.get('status')}`, reason `{r.get('reason')}`, "
                             f"{u.get('calls')} calls, {u.get('input_tokens')}/{u.get('output_tokens')} tokens, ${u.get('known_cost_usd')}")
            L.append("")
            continue
        L.append(f"### Step {k}")
        for r in evs:
            ev = r.get("event")
            if ev == "model":
                u = r.get("usage") or {}
                tok_in += u.get("input_tokens") or 0; tok_out += u.get("output_tokens") or 0
                L.append(f"- model call: in={u.get('input_tokens')} out={u.get('output_tokens')} ({r.get('seconds')} s)")
            elif ev == "tool":
                args = r.get("args") or {}
                target = args.get("path") or args.get("paths") or args.get("argv") or ""
                ok = r.get("outcome") == "ok"
                tools[r.get("tool")] += 1
                if r.get("tool") in ("write_file", "apply_patch") and ok:
                    files_written[str(target)] += 1
                if r.get("tool") == "read_file":
                    for pth in (target if isinstance(target, list) else [target]):
                        reads[str(pth)] += 1
                mark = "OK" if ok else "**ERR**"
                L.append(f"- `{r.get('tool')}({_short(target, 90)})` -> {mark}" + ("" if ok else f": {_short(r.get('result'), 260)}"))
                if not ok:
                    code = _err_code(r.get("result"))
                    errors[code] += 1
                    repeats += 1 if code == last_err else 0
                    last_err = code
                else:
                    last_err = None
            elif ev in ("smoke", "integration_phase"):
                g = r.get("gates") or {}
                gate_history.append((k, g))
                for gate, val in g.items():
                    if val == "passed":
                        first_pass.setdefault(gate, k)
                L.append(f"- checks ({ev}): " + ", ".join(f"{a}={b}" for a, b in g.items()) +
                         (f"  reason=`{r.get('reason')}`" if r.get("reason") not in (None, "None") else ""))
            elif ev == "local_failure":
                d = r.get("diagnostics") or {}
                diag = d.get("diagnostics") if isinstance(d, dict) else d
                if r.get("source") == "run_shell" and isinstance(d, dict):
                    diag = " | ".join(x for x in (d.get("diagnostics") or []) if x)
                L.append(f"- failure ({r.get('source')}): {_short(diag or d, 300)}")
            else:
                L.append(f"- {ev}: {_short({x: y for x, y in r.items() if x not in ('ts', 'attempt_id', 'event', 'step')}, 200)}")
        L.append("")

    # ---- tester
    L += ["## 3. Tester actions", ""]
    for x in (results or {}).get("results", []):
        L.append(f"### {x.get('test_id')}: expect `{x.get('expected')}` -> **{x.get('status')}** "
                 f"(retries {x.get('input_retries', 0)}, {x.get('duration_seconds')} s)")
        for a in x.get("action_results", []):
            extra = ", ".join(f"{k2}={a[k2]}" for k2 in ("key", "seconds", "window_focused", "sent_with", "retry", "error") if k2 in a)
            L.append(f"- {a.get('type')} [{a.get('status')}] {extra}")
        out = Path(x.get("runtime_evidence", {}).get("stdout_file", "") or "")
        if out.is_file():
            tail = [l for l in out.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()][-6:]
            L.append("- game printed (last lines): " + " / ".join(f"`{_short(l, 60)}`" for l in tail))
        L.append(f"- verdict: {x.get('reason')}")
        L.append("")

    # ---- loop analysis
    n_steps = len([k for k in steps if k])
    n_err = sum(errors.values())
    L += ["## 4. Loop analysis (where the steps went)", "",
          "| Metric | Value |", "|---|---|",
          f"| Coder steps used | {n_steps} |",
          f"| Tool calls (by tool) | {dict(tools)} |",
          f"| Failed tool calls | {n_err} ({(100 * n_err // max(1, sum(tools.values())))}% of calls) |",
          f"| Same error repeated back-to-back | {repeats} time(s) |",
          f"| First step each check passed | {first_pass or 'none'} |",
          f"| Check runs | {len(gate_history)} |",
          f"| Tokens in/out (sum of calls) | {tok_in}/{tok_out} |", "",
          "**Errors by type** (most common first):", ""]
    L += [f"- `{c}`: {n}" for c, n in errors.most_common()] or ["- none"]
    L += ["", "**Files rewritten/patched most** (churn):", ""]
    L += [f"- `{f}`: {n} write(s)" for f, n in files_written.most_common(6)] or ["- none"]
    L += ["", "**Files read most:**", ""]
    L += [f"- `{f}`: {n} read(s)" for f, n in reads.most_common(6)] or ["- none"]
    hints = []
    if errors.get("line_range_requires_exactly_one_path"):
        hints.append("multi-file reads with a line range failed: check the multi-read fix is in tools_coder.py")
    if errors.get("godot3_api"):
        hints.append("Godot 3 names were caught at write time; if this is large, strengthen the playbook list")
    if errors.get("unplanned_godot_resource"):
        hints.append("res://game/ paths or unplanned files: the Planner file list or the path rule is being ignored")
    if errors.get("patch_context_not_unique_or_missing", 0) >= 3:
        hints.append("apply_patch keeps missing: the coder should rewrite the file with write_file after 2 misses")
    if files_written and files_written.most_common(1)[0][1] >= 6:
        hints.append(f"heavy churn on {files_written.most_common(1)[0][0]}: likely the hardest file (often a hand-written scene)")
    if repeats >= 3:
        hints.append("the same error repeated several times in a row: a loop the coder could not break")
    L += ["", "**Hints for loop engineering:**", ""] + ([f"- {h}" for h in hints] or ["- no obvious loop pattern"])
    return "\n".join(L) + "\n", {"steps": n_steps, "tool_calls": dict(tools), "failed_tool_calls": n_err,
                                 "errors_by_type": dict(errors), "back_to_back_repeats": repeats,
                                 "first_step_check_passed": first_pass, "most_written_files": dict(files_written.most_common(6))}



# ---------------------------------------------------------------------------
# Extra diagnostics for improving the agents (settings snapshot, full check output,
# final boot log, human check template, cross-run index)
# ---------------------------------------------------------------------------
WATCHED_FILES = [  # prompts / guardrails / agents whose version matters for comparing runs
    "master_planner/planner/resources/planner_prompt.txt", "master_planner/planner/call_planner.py",
    "master_planner/asset/planner.py", "coder_agent_adhoc/resources/prompt_coder.txt",
    "coder_agent_adhoc/adapters/godot.py", "coder_agent_adhoc/adapters/pygame.py",
    "coder_agent_adhoc/tools/tools_coder.py", "eval_generator_module/eval_generator/generator.py",
    "bo_v4_tester_v1/bo_v4_tester/tester.py", "triage_agent/triage.py", "run_pipeline.py",
]


def settings_snapshot():
    """Which versions/settings produced this run. API keys are never included."""
    import importlib.metadata as md
    env = {k: v for k, v in env_with_keys().items()
           if (k.startswith(("CODER_", "PLANNER_", "ASSET_", "EVAL_", "TRIAGE_", "GODOT")) or k in ("OPENROUTER_MODEL",))
           and not k.endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))}
    vers = {"python": platform.python_version(), "os": platform.platform()}
    for pkg in ("pygame", "pyautogui", "langchain-core", "langchain-openai", "openai"):
        try:
            vers[pkg] = md.version(pkg)
        except Exception:
            pass
    godot = env.get("GODOT_BINARY")
    if godot:
        try:
            vers["godot"] = subprocess.run([godot, "--headless", "--version"], capture_output=True, text=True,
                                           timeout=60).stdout.strip().splitlines()[-1]
        except Exception as e:
            vers["godot"] = f"unavailable: {e}"
    hashes = {}
    for f in WATCHED_FILES:
        fp = ROOT / f
        if fp.is_file():
            hashes[f] = hashlib.sha256(fp.read_bytes()).hexdigest()[:12]
    pipeline = {k: (str(v) if isinstance(v, (Path, set)) else v) for k, v in globals().items()
                if k.isupper() and k in ("SPEC_FILE", "DRY_RUN_ASSETS", "STARTUP_WAIT", "TESTER_LIMIT", "FAIL_STATUSES",
                                         "USE_TRIAGE", "MAX_ROUNDS", "TRIAGE_MIN_CONFIDENCE", "DONE_IF_ANY_PASS")}
    return {"run_id": RUN_ID, "pipeline_settings": pipeline, "env_settings": env, "versions": vers,
            "file_versions_sha256_12": hashes}


def full_check_output():
    """Every coder check (syntax / boot / smoke) with the complete engine diagnostics, untruncated."""
    ids = set(STATE.get("coder_attempts", []))
    L = [f"# Full check output: {RUN_ID}", "",
         "Every syntax/boot check the coder ran, with the complete engine output it received.", ""]
    for r in _jsonl(ROOT / "traces" / "coder_attempts.jsonl"):
        if r.get("attempt_id") not in ids or r.get("event") not in ("smoke", "integration_phase", "local_failure"):
            continue
        if r.get("event") == "local_failure" and r.get("source") not in ("run_shell", "smoke", "integration_phase"):
            continue
        d0 = r.get("diagnostics") if isinstance(r.get("diagnostics"), dict) else {}
        g = r.get("gates") or d0.get("gates")
        d = r.get("diagnostics") if isinstance(r.get("diagnostics"), dict) else {}
        cmds = d.get("commands") or []
        if d.get("diagnostics") and not cmds:
            cmds = [d]
        if not cmds and r.get("evidence"):
            cmds = r.get("evidence") if isinstance(r.get("evidence"), list) else []
        if not any(isinstance(c, dict) and any(str(x).strip() for x in (c.get("diagnostics") or [])) for c in cmds):
            continue   # nothing printed by the engine for this event
        L.append(f"## Step {r.get('step')}: {r.get('event')} ({r.get('source', '')})  gates={g}")
        for c in cmds:
            if not isinstance(c, dict):
                continue
            L.append(f"- command: `{' '.join(map(str, c.get('argv', [])))[:200]}`  returncode={c.get('returncode')} "
                     f"reason={c.get('reason')} seconds={c.get('seconds')}")
            lines = [x for x in (c.get("diagnostics") or []) if str(x).strip()]
            if lines:
                L += ["```"] + [str(x) for x in lines] + ["```"]
        L.append("")
    return "\n".join(L) + "\n"


def final_boot_log():
    """Run the finished game headless for FINAL_BOOT_SECONDS and keep its complete stdout/stderr."""
    if not FINAL_BOOT_SECONDS or not STATE.get("coder_ready"):
        return None
    try:
        cmd = launch_command()
        plan = json.loads((ROOT / "plans" / "coder_plan.json").read_text(encoding="utf-8"))
        rend = plan["profile"]["renderer"]
        rend = rend if isinstance(rend, str) else rend.get("value")
        env = env_with_keys()
        if rend == "godot":
            godot = os.getenv("GODOT_BINARY") or "godot"
            args = [godot, "--headless", "--path", "game", "--quit-after", str(int(FINAL_BOOT_SECONDS * 60))]
        else:
            env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
            args = [a.strip('"') for a in cmd.split(" ")]
        p = subprocess.Popen(args, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
        try:
            out, err = p.communicate(timeout=FINAL_BOOT_SECONDS + 20)
            code = p.returncode
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
            code = "killed after timeout (normal for a running game)"
        return (f"# Final boot log: {RUN_ID}\n\ncommand: {' '.join(args)}\nexit: {code}\n\n"
                f"## stdout\n```\n{out}\n```\n\n## stderr\n```\n{err}\n```\n")
    except Exception as e:
        return f"# Final boot log\n\nfailed to run: {type(e).__name__}: {e}\n"


HUMAN_CHECK_TEMPLATE = """# Human check: {title} ({run_id})

Play the game (double-click play.bat in the gallery, or `python play.py` in BOV5), then fill this in.
It is the ground truth for comparing against the automated Tester result: **{outcome}**

| Question | Answer (yes / no / partly) | Notes |
|---|---|---|
| Game launches without errors | | |
| Every control does what the manual says | | |
| Main mechanic works (scoring, collisions, enemies...) | | |
| Win / game over / restart work | | |
| Looks right (sprites, layout, text readable) | | |

**Overall verdict** (works / partly works / broken): 

**Do the automated test results match what you saw?** (yes / no: which test was wrong?):
"""


def append_runs_index(summary, metrics):
    """Add one row per run to runs_index.csv (created with a header the first time)."""
    try:
        p, c, e, t = metrics["planner"], metrics["logic_coder"], metrics["eval_generator"], metrics["runtime_tester"]
        loop = metrics.get("loop_analysis") or {}
        errs = loop.get("errors_by_type") or {}
        counts = t.get("counts") or {}
        row = {
            "run_id": RUN_ID, "spec_file": Path(STATE.get("spec_file", "")).name, "game_title": p.get("game_title"),
            "engine": p.get("renderer"), "outcome": summary.get("outcome"),
            "total_cost_usd": summary.get("total_cost_usd"), "elapsed_s": summary.get("elapsed_s"),
            "planner_attempts": p.get("attempts"), "planner_cost": p.get("cost_usd"),
            "asset_strategy": metrics["asset_agent"].get("strategy"), "assets": metrics["asset_agent"].get("assets"),
            "asset_cost": metrics["asset_agent"].get("cost_usd"),
            "coder_status": c.get("status"), "coder_reason": c.get("reason"), "coder_steps": loop.get("steps") or c.get("steps"),
            "coder_cost": c.get("cost_usd_metered"), "coder_tokens_in": c.get("tokens_in"), "coder_tokens_out": c.get("tokens_out"),
            "failed_tool_calls": loop.get("failed_tool_calls"),
            "top_error": max(errs, key=errs.get) if errs else "",
            "first_boot_pass_step": (loop.get("first_step_check_passed") or {}).get("boot", ""),
            "controls_found": len(e.get("controls_found") or []),
            "tests_total": sum(counts.values()) if counts else 0, "tests_pass": counts.get("PASS", 0),
            "tests_fail": counts.get("FAIL", 0) + counts.get("ERROR", 0),
            "triage": "on" if USE_TRIAGE else "off", "human_verdict": "",
        }
        new = not RUNS_INDEX.is_file()
        with RUNS_INDEX.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)
        print(f"[REVIEW]   runs_index.csv +1 row ({RUNS_INDEX.name})", flush=True)
    except Exception as ex:
        print(f"[REVIEW]   runs index failed: {type(ex).__name__}: {ex}", flush=True)


def export_review(summary):
    """Copy every agent artifact + metrics into game/_review/, then zip game/ to exports/<run_id>_<title>.zip."""
    try:
        out = ROOT / "game" / "_review"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        tr, pl = ROOT / "traces", ROOT / "plans"
        (out / "1_planner").mkdir()
        (out / "1_planner" / "spec.txt").write_text(SPEC, encoding="utf-8")
        if STATE.get("spec_file"):
            _copy(STATE["spec_file"], out / "1_planner" / Path(STATE["spec_file"]).name)
        for f in ("plan.json", "coder_plan.json"):
            _copy(pl / f, out / "1_planner" / f)
        _copy(tr / "planner_attempts.jsonl", out / "1_planner" / "planner_attempts.jsonl")
        _copy(pl / "asset_manifest.json", out / "2_assets" / "asset_manifest.json")
        _copy(tr / "coder_result.json", out / "3_coder" / "coder_result.json")
        _copy(pl / "play_manual.json", out / "3_coder" / "play_manual.json")
        ids = set(STATE.get("coder_attempts", []))
        rows = [l for l in (tr / "coder_attempts.jsonl").read_text(encoding="utf-8").splitlines()
                if ids and any(i and i in l for i in ids)] if (tr / "coder_attempts.jsonl").is_file() else []
        (out / "3_coder").mkdir(exist_ok=True)
        (out / "3_coder" / "coder_trace.jsonl").write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
        if STATE.get("suite"):
            _copy(STATE["suite"], out / "4_eval" / "suite.json")
        if STATE.get("results"):
            _copy(STATE["results"], out / "5_tester" / "test_results.json")
            _copy(Path(STATE["results"]).parent / "evidence", out / "5_tester" / "evidence")
        for f in TRACE_DIR.iterdir():
            _copy(f, out / "6_pipeline" / f.name)
        metrics = build_metrics(summary)
        (out / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
        (out / "README.md").write_text(review_markdown(metrics), encoding="utf-8")
        try:
            log_md, loop = build_turn_log(summary)                       # turn-by-turn debug log
            (out / "DEBUG_TURNS.md").write_text(log_md, encoding="utf-8")
            metrics["loop_analysis"] = loop
            (out / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            print(f"[REVIEW]   turn log failed: {type(e).__name__}: {e}", flush=True)
        for name, make in (("settings.json", lambda: json.dumps(settings_snapshot(), indent=2, default=str)),
                           ("CHECK_OUTPUT.md", full_check_output),
                           ("FINAL_BOOT.md", final_boot_log)):
            try:
                text = make()
                if text:
                    (out / name).write_text(text, encoding="utf-8")
            except Exception as e:
                print(f"[REVIEW]   {name} failed: {type(e).__name__}: {e}", flush=True)
        (out / "HUMAN_CHECK.md").write_text(HUMAN_CHECK_TEMPLATE.format(
            title=metrics["planner"].get("game_title"), run_id=RUN_ID, outcome=summary.get("outcome")), encoding="utf-8")
        append_runs_index(summary, metrics)

        title = "".join(ch if ch.isalnum() else "_" for ch in str(metrics["planner"].get("game_title") or "game"))[:40]
        zpath = ROOT / "exports" / f"{RUN_ID}_{title}.zip"
        zpath.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in (ROOT / "game").rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts and ".godot" not in f.parts:
                    z.write(f, f.relative_to(ROOT))
        print(f"[REVIEW]   game/_review/README.md  +  {zpath.relative_to(ROOT)}", flush=True)
    except Exception as e:
        print(f"[REVIEW]   export failed: {type(e).__name__}: {e}", flush=True)


def copy_to_gallery(outcome):
    """Copy the built game (and game/_review) into the gallery, sorted by engine, with a play.bat."""
    try:
        plan = json.loads((ROOT / "plans" / "coder_plan.json").read_text(encoding="utf-8"))
        rend = plan["profile"]["renderer"]
        rend = rend if isinstance(rend, str) else rend.get("value")
        title = str(plan.get("game_title") or "Untitled game")
        safe = "".join(ch if ch.isalnum() or ch in " -_()" else "_" for ch in title).strip() or "game"
        engine_dir = GALLERY_DIR / {"godot": "Godot", "pygame": "Pygame"}.get(rend, "Terminal")
        dest = engine_dir / safe
        if dest.exists():
            dest = engine_dir / f"{safe} ({RUN_ID})"
        skip = shutil.ignore_patterns("__pycache__", ".godot", "*.pyc")
        entry = plan["architecture"]["entry_point"]
        if rend == "godot":
            # Godot: project.godot sits at the top of the game folder; open this folder in Godot or run play.bat
            shutil.copytree(ROOT / "game", dest, ignore=skip)
            godot = os.getenv("GODOT_BINARY") or "godot"
            bat = (f'@echo off\r\ncd /d "%~dp0"\r\n"{godot}" --headless --path . --import >nul 2>&1\r\n'
                   f'"{godot}" --path .\r\n')
        else:
            # pygame/terminal: keep the game/ package so `python -m game.<entry>` works
            shutil.copytree(ROOT / "game", dest / "game", ignore=skip)
            module = entry[:-3].replace("/", ".") if entry.endswith(".py") else entry
            bat = f'@echo off\r\ncd /d "%~dp0"\r\npython -m {module}\r\npause\r\n'
        (dest / "play.bat").write_bytes(bat.encode("utf-8"))
        (dest / "GAME_INFO.md").write_text(
            f"# {title}\n\n- Engine: {rend}\n- Built: run {RUN_ID}\n- Result: {outcome}\n"
            f"- Spec file: {Path(STATE.get('spec_file', '')).name}\n- Play: double-click `play.bat`\n\n## Spec\n\n{SPEC}\n",
            encoding="utf-8")
        print(f"[GALLERY]  {dest}", flush=True)
    except Exception as e:
        print(f"[GALLERY]  copy failed: {type(e).__name__}: {e}", flush=True)


def finish(outcome, **extra):
    by_agent = {}
    for r in COST_ROWS:
        if r["cost_usd"] is not None:
            by_agent[r["agent"]] = round(by_agent.get(r["agent"], 0) + r["cost_usd"], 5)
    known = [r["cost_usd"] for r in COST_ROWS if r["cost_usd"] is not None]
    total = round(sum(known), 4) if known else None
    summary = {"run_id": RUN_ID, "spec_file": str(STATE.get("spec_file", "")), "outcome": outcome, "turns": TURN,
               "elapsed_s": round(time.monotonic() - STARTED, 1),
               "total_cost_usd": total, "cost_by_agent": by_agent,
               "coder_cost_usd_self_reported": round(COST["coder"], 4),
               "routing": ROUTES, "cost_by_stage": COST_ROWS, **extra}
    (TRACE_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    banner(f"RESULT: {outcome}")
    if EXPORT_REVIEW:
        export_review(summary)
    if COPY_TO_GALLERY and STATE.get("coder_ready"):
        copy_to_gallery(outcome)
    print_cost_report(by_agent, total)
    print("\n" + json.dumps({k: v for k, v in summary.items() if k not in ("cost_by_stage",)}, indent=2, default=str))
    print(f"\nTrace: {TRACE_FILE.relative_to(ROOT)}")
    return 0 if outcome == "GAME READY" else 1


def load_spec():
    """Read a spec .md from game_specs/. Only the text under '## Spec' goes to the Planner
    (if there is no '## Spec' heading, the whole file minus '#' heading lines is used)."""
    name = sys.argv[1] if len(sys.argv) > 1 else SPEC_FILE
    path = Path(name)
    if not path.is_absolute():
        path = SPEC_DIR / name
    if path.suffix == "":
        path = path.with_suffix(".md")
    if not path.is_file():
        found = sorted(p.name for p in SPEC_DIR.glob("*.md") if p.name.lower() != "readme.md") if SPEC_DIR.is_dir() else []
        sys.exit(f"Spec file not found: {path}\nAvailable in {SPEC_DIR}: {', '.join(found) or '(none)'}")
    text = path.read_text(encoding="utf-8")
    m = re.search(r"(?ims)^##\s*spec\s*$(.*?)(?=^##\s|\Z)", text)
    body = m.group(1) if m else "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    spec = " ".join(body.split())
    if not spec:
        sys.exit(f"Spec file is empty: {path}")
    STATE["spec_file"] = path
    return spec


def main():
    global SPEC
    SPEC = load_spec()
    banner(f"PIPELINE {RUN_ID}  (max {MAX_ROUNDS} test/fix rounds, control-only tests)")
    (ROOT / "traces").mkdir(exist_ok=True)
    (ROOT / "traces" / "original_game_spec.txt").write_text(SPEC, encoding="utf-8")   # Triage needs it for re-plans
    trace("start", "ok", detail=f"spec={STATE['spec_file'].name} ({len(SPEC)} chars)")

    banner("1. PLANNER + ASSET AGENT")
    stage_plan_and_assets()

    banner("2. LOGIC CODER (initial build)")
    _, coder = stage_coder()
    if coder.get("status") != "ready_for_testing":
        return finish("STOPPED: coder did not finish", reason=coder.get("reason"))

    suite_no = 1
    banner("3. EVAL GENERATOR")
    suite = stage_eval(f"run{RUN_ID}-s{suite_no}")
    if suite is None:
        return finish("STOPPED: eval generator failed")

    for round_no in range(1, MAX_ROUNDS + 1):
        banner(f"4. RUNTIME TESTER  (round {round_no}/{MAX_ROUNDS})")
        results_path, counts = stage_tester(suite, round_no)
        if results_path is None:
            return finish("STOPPED: tester failed")
        failing = sum(v for k, v in counts.items() if k in FAIL_STATUSES)
        review = counts.get("NEEDS_REVIEW", 0)
        passed = counts.get("PASS", 0)
        if failing == 0:
            trace("decision", "no errors", round=round_no, detail=f"needs_review={review}")
            return finish("GAME READY", rounds=round_no, needs_human_review=review,
                          results=results_path.relative_to(ROOT).as_posix())
        if DONE_IF_ANY_PASS and passed > 0:
            trace("decision", "done (partial)", round=round_no, detail=f"{passed} passed, {failing} failing")
            return finish(f"DONE: {passed} passed, {failing} failed", rounds=round_no, counts=counts,
                          results=results_path.relative_to(ROOT).as_posix())
        trace("decision", "errors found", round=round_no, detail=f"{failing} failing test(s)")

        if not USE_TRIAGE:
            return finish(f"DONE: {passed} passed, {failing} failed (triage disabled)", rounds=round_no, counts=counts,
                          results=results_path.relative_to(ROOT).as_posix())

        if round_no == MAX_ROUNDS:
            return finish("STOPPED: max rounds reached", rounds=round_no, last_counts=counts)

        banner(f"5. TRIAGE AGENT  (round {round_no})")
        rep = stage_triage(results_path, round_no)
        if rep is None:
            return finish("STOPPED: triage failed")
        route, cb = rep.get("diagnosis", {}).get("route"), rep.get("callback", {})
        if cb.get("status") in ("not_called", "blocked", "error", "not_needed"):
            return finish(f"STOPPED: triage did not fix ({cb.get('status')})", route=route, reason=cb.get("reason") or cb.get("error"))

        if route == "planner":
            # Triage re-ran the Planner only; the plan changed, so rebuild assets + code
            # and generate a NEW suite (old tests belong to the old plan).
            banner("   re-plan: rebuilding assets and code")
            from master_planner.run import run_asset_agent
            before = usage_now()
            run_asset_agent(json.loads((ROOT / "plans" / "plan.json").read_text(encoding="utf-8")))
            add_cost("asset_agent (rebuild)", before, usage_now(settle=True), round_no, route)
            trace("asset_agent", "rebuilt", round=round_no)
            _, coder = stage_coder("logic_coder (rebuild)", round_no, route)
            if coder.get("status") != "ready_for_testing":
                return finish("STOPPED: coder rebuild after re-plan failed", reason=coder.get("reason"))
            suite_no += 1
            suite = stage_eval(f"run{RUN_ID}-s{suite_no}", round_no, route)
            if suite is None:
                return finish("STOPPED: eval generator failed after re-plan")
        elif route == "logic_coder":
            cr = cb.get("coder_result") or {}
            cost = (cr.get("usage") or {}).get("known_cost_usd") or 0
            COST["coder"] += cost
            trace("coder_repair", cr.get("status", cb.get("status")), round=round_no, reason=cr.get("reason"), cost=f"${cost:.4f}")
            # same suite on purpose: retest must include previously passed tests
        elif route == "asset":
            trace("asset_agent", cb.get("status"), round=round_no)
        # loop -> Runtime Tester again


if __name__ == "__main__":
    try:
        import pyautogui  # noqa: F401
    except Exception:
        print("[PIPELINE] note: pyautogui not installed -> the Tester cannot press keys in pygame/godot "
              "windows (tests become BLOCKED). Install with: python -m pip install pyautogui\n")
    raise SystemExit(main())