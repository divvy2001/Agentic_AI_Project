# Bo's Project V4 — Runtime Tester v1

This is a separate module; it does **not** change the Eval Generator.

## Capabilities
- Loads existing `suite.json` files.
- Runs tests marked `ready_for_validator`; records `not_testable` cases as `NOT_RUN`.
- Executes conservative `press`, `input`, `wait`, `click`, `key_down`, `key_up`, `observe`, and `restart` actions where supported.
- Captures process stdout/stderr, return code, action results, optional screenshots, per-test evidence JSON, and a project file/hash inventory.
- Adds low-confidence hints for likely asset/runtime/planner signals for the future Triage Agent.

## Limitations to understand
- You must supply the launch command; it is not safe/reliable to infer one for every project.
- Terminal input uses stdin and works only if the game reads stdin normally.
- Pygame/Godot keyboard, mouse and screenshots need optional `pyautogui`.
- `screen_text` currently means process output, not OCR from pixels.
- `game_state` needs game-side instrumentation; generic external inspection is not available.
- Automated PASS/FAIL is conservative: `expected` must be a literal substring of stdout/log. Visual and non-literal checks require `NEEDS_REVIEW` or game-specific assertions.
- Unsupported actions make the test `BLOCKED`, not a game failure.
- `script_path` in a suite is never executed. The user-supplied `--launch-command` is the only command executed.
- Triage hints are not definitive cause attribution.

## Setup (PowerShell)
Core runner uses Python standard library only. Optional GUI support:
```powershell
py -m pip install pyautogui
```

## Run examples from Bo V4 project root
Terminal/Pygame Python game (adjust path to your actual entry point):
```powershell
py bo_v4_tester\tester.py --project-root . --suite traces\eval\eval-v1\suite.json --launch-command "py game\main.py" --limit 2
```

Godot (if `godot` is on PATH; adjust project folder):
```powershell
py bo_v4_tester\tester.py --project-root . --suite traces\eval\eval-v1\suite.json --launch-command "godot --path game" --limit 2
```

If `--suite` is omitted, the newest `traces/eval/*/suite.json` is selected.

## Output
`traces/eval/<suite_version>/test_run_<timestamp>/`
- `test_results.json`: summary, per-test statuses, evidence pointers, triage hints
- `project_inventory.json`: project file paths, sizes and hashes
- `evidence/<test_id>/evidence.json`: actions, observations, status and hints
- `evidence/<test_id>/stdout.log`, `stderr.log`, and optional screenshot

Statuses: `PASS`, `FAIL`, `BLOCKED`, `INCONCLUSIVE`, `NEEDS_REVIEW`, `NOT_RUN`, `ERROR`.

## Triage workflow
The downstream Triage Agent should correlate the original game description, `plans/coder_plan.json`, `plans/play_manual.json`, `plans/asset_manifest.json`, generated code/assets, `test_results.json`, and evidence folders. Missing-resource logs suggest an asset hypothesis; exceptions/state mismatches suggest a mechanic/code hypothesis; a feature missing from the plan despite being in the original brief suggests a planner hypothesis. Multiple causes may apply.
