# Run review: 20261027_210628

**Outcome:** DONE: 1 passed, 3 failed (triage disabled)  
**Total time:** 741.9 s  
**Total cost:** $0.2562

## Spec

```
Create a tiny one-screen 2D fighting game called "Dojo Duel". The player controls a red-belt martial artist on the left; a blue-belt rival controlled by the computer stands on the right. Generate exactly two small image assets: the red-belt fighter and the blue-belt fighter, both facing sideways. Use a plain wooden-brown floor and a light background colour instead of a background image. Both fighters stand on the floor with gravity. The Left and Right arrow keys walk the player, the Up arrow jumps, and Space throws a punch. Punches knock the opponent back with realistic physics: the hit fighter keeps its momentum, slides along the floor and bounces off the screen edges. Each punch plays a short tweened lunge forward and back, and a hit fighter flashes white briefly. A punch that lands removes 10 health. The rival walks toward the player and punches when close, with a one-second pause between punches. Each fighter has 100 health shown as a bar at the top of the screen. When a fighter reaches 0 health, show WIN or GAME OVER and freeze the game. Press R to restart the fight and Escape to quit. Print a line to the console every time a control takes effect: MOVE LEFT, MOVE RIGHT, JUMP, PUNCH, RESTART and QUIT, and print WIN or GAME OVER when the fight ends. No sounds. Keep it to one small main scene with every node created from as few scripts as possible.
```

## Agents

| Agent | Status | Time (s) | Tokens in/out | Cost ($) | Notes |
|---|---|---|---|---|---|
| Planner | success | 57.7 (incl. assets) | 12650/8306 | 0.0 | 2 attempt(s), 23 requirements, renderer godot |
| Asset Agent | ai_art | – | – | 0.05105 | 2 asset(s) |
| Logic Coder | ready_for_testing | 624.9 | 578356/48039 | 0.20514 (self-reported 0.16639179999999998) | 48 steps, 48 calls, openai/gpt-5-mini |
| Eval Generator | ok | 21.1 | – | 0.0 | 6 controls found |
| Runtime Tester | done | 37.8 | – | 0 | {'FAIL': 3, 'PASS': 1} |
| Triage / Router | off | – | – | – | 0 decision(s) |

## Control tests

| Test | Expected line | Result | Retries | Window focused |
|---|---|---|---|---|
| C01 | `MOVE LEFT` | FAIL | 2 | [True, True, True] |
| C02 | `MOVE RIGHT` | FAIL | 2 | [True, True, True] |
| C03 | `JUMP` | FAIL | 2 | [True, True, True] |
| C04 | `PUNCH` | PASS | 0 | [True] |

## Files in this folder

- `metrics.json`: all numbers above, per agent
- `1_planner/`: spec, plan.json, coder_plan.json, planner_attempts.jsonl
- `2_assets/`: asset_manifest.json
- `3_coder/`: coder_result.json, coder_trace.jsonl (this run's steps only), play_manual.json
- `4_eval/`: suite.json (controls + tests)
- `5_tester/`: test_results.json + evidence/ (stdout/stderr per test)
- `6_pipeline/`: pipeline_trace.jsonl, summary.json, stage logs, triage reports
