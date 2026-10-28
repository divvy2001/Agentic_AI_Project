"""
test.py

Standalone smoke test for the real master_planner pipeline. It does not
reimplement any pipeline logic — it imports run() from master_planner.run
and calls it directly, so this always exercises the exact same code path a
real build uses (same planner call, same asset-agent wiring, same real
OpenRouter art call once a key is configured).

Edit the variables below, then just run:
    python test.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from master_planner.run import run

# ---------------------------------------------------------------------------
# Edit these to control the test. No CLI args — everything lives here.
# ---------------------------------------------------------------------------

# The game spec to test with.
SPEC = (
    "Create a tiny one-screen game called \"Moon Hopper\". "
    "The player flies a small lander that starts hovering near the top of the screen above a flat landing pad. "
    "Gravity constantly pulls the lander down. Holding the Up arrow fires the thruster and pushes the lander in the direction it is facing; "
    "the Left and Right arrow keys rotate it. The lander has real physics: it keeps its momentum and drifts, and it bounces off the left and right screen edges. "
    "Touching down on the pad slowly and upright wins; hitting the ground too fast or tilted crashes. "
    "Show the current speed in the top-left corner, and show a small flame shape behind the lander while thrusting. "
    "When the player wins or crashes, show WIN or GAME OVER and freeze the game. "
    "Press R to restart from the top and Escape to quit. "
    "Print a line to the console every time a control takes effect: THRUST, ROTATE LEFT, ROTATE RIGHT, RESTART and QUIT, "
    "and print WIN or GAME OVER when the game ends. "
    "Use plain coloured shapes only; no images or sounds. Keep it to one scene and as few scripts as possible."
)
# True  -> scripted plan, no LLM call (free, instant, but SPEC's text is
#          ignored since the scripted plan is hardcoded).
# False -> real planner LLM call using SPEC above (costs tokens).
DRY_RUN_PLANNER = False

# True  -> procedural art only, no OpenRouter call.
# False -> real OpenRouter image call per sprite (costs image credits).
DRY_RUN_ASSETS = False

# True  -> print the full rendered system prompt before the first attempt.
SHOW_PROMPT = False

# True  -> after the planner/asset run, also run the standalone Coder agent
#          (coder_agent/) against plans/coder_plan.json to write and debug
#          an actual game into game/. Real LLM call, costs tokens.
# False -> skip the Coder agent entirely (planner + assets only).
RUN_CODER = True

# True  -> construct the Coder agent (reads plan, builds the LLM client)
#          but stop before the first real LLM call. Only used if RUN_CODER
#          is True — lets you smoke-test the wiring without spending tokens
#          or needing network access.
CODER_DRY_RUN = False


if __name__ == "__main__":
    print(f"[TEST] spec: {SPEC!r}")
    print(f"[TEST] dry_run_planner={DRY_RUN_PLANNER}  dry_run_assets={DRY_RUN_ASSETS}")

    plan = run(
        SPEC,
        dry_run_planner=DRY_RUN_PLANNER,
        dry_run_assets=DRY_RUN_ASSETS,
        print_prompt=SHOW_PROMPT,
    )

    print("\n[TEST] done — plan returned for:", plan.get("game_title"))

    if RUN_CODER:
        from coder_agent_adhoc.initial_build import run_initial_build

        print(f"\n[TEST] running coder_agent (dry_run={CODER_DRY_RUN})...")
        coder_result = run_initial_build(dry_run=CODER_DRY_RUN)
        print("[TEST] coder_agent result:", coder_result)
        if coder_result.get('status') not in ('ready_for_testing', 'dry_run'):
            print("[CODER] INCOMPLETE — this game is not ready to open.")
            print("[CODER] reason:", coder_result.get('reason'))
            print("[CODER] missing files:", coder_result.get('file_inventory', {}).get('missing', []))
            if coder_result.get('attempt_id'):
                print("[CODER] Continue this build without rerunning Planner/Asset:")
                print("python -m coder_agent_adhoc.initial_build --resume " + coder_result['attempt_id'])
            raise SystemExit(2)
        if coder_result.get('play_session', {}).get('status') == 'failed':
            print("[CODER] Build returned, but opening the play window failed:", coder_result['play_session'].get('reason'))
            raise SystemExit(3)
