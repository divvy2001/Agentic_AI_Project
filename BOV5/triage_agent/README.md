# Bo's Project V4 — Triage Agent

The Triage Agent reads the Runtime Tester's `test_results.json`, reviews the attached runtime evidence and current plan/asset manifest, then routes the issue to one of the existing agents:

- `asset` → `master_planner.run.run_asset_agent(plan)`
- `planner` → `master_planner.planner.call_planner.run_planner(original_spec)`
- `logic_coder` → `coder_agent_adhoc.repair.run_repair(feedback_path)`
- `unknown` → no callback; ask for better evidence instead of guessing

It does not replace or modify the current Eval Generator or Tester.

## Run from the project root

Use the project's Python environment and run:

```powershell
py -m triage_agent.triage --dry-run
```

This classifies the newest `traces/eval/*/test_run_*/test_results.json` without invoking an agent. In dry-run mode it uses conservative deterministic diagnosis and does not call OpenRouter.

Run diagnosis and allow it to call the selected agent:

```powershell
py -m triage_agent.triage
```

The Triage Agent reads `PLANNER_OPENROUTER_API_KEY` from the environment or project `.env`. If it is not present, it prompts for an OpenRouter key with hidden input. Default model: `openai/gpt-4.1-mini`.

To use a specific Tester result file:

```powershell
py -m triage_agent.triage --test-results "traces\eval\eval-v1\test_run_20261026_120000\test_results.json"
```

To route a Planner issue, supply the original user game specification as a project-local text file. The default auto-detection checks `traces/original_game_spec.txt`, `plans/game_spec.txt`, `game_spec.txt`, and `traces/game_spec.txt`.

```powershell
py -m triage_agent.triage --spec-file "traces\original_game_spec.txt"
```

The original spec is required because Planner reruns must be grounded in the original request, not reconstructed from failure logs.

Other options:
- `--no-llm`: deterministic fallback diagnosis only.
- `--model openai/gpt-4.1-mini`: change the OpenRouter model.
- `--min-confidence 0.75`: raise the minimum confidence needed before callback.
- `--report traces/triage/my_report.json`: choose report output.
- `--dry-run`: do not invoke agents; Logic Coder feedback can be prepared for inspection.

## Outputs

`traces/triage/triage_<timestamp>.json` records:
- diagnosis route, confidence, reason and supporting evidence
- method used (OpenRouter or deterministic fallback)
- callback chosen and callback result
- blocked/error reason if required inputs are missing

For a Logic Coder callback, the module creates the strict feedback file expected by the existing repair gate:
`traces/eval/<suite_version>/test_results.json`

It includes only actionable `FAIL`/`ERROR` tests with existing project-local evidence. It preserves previously passed test IDs. The repair gate is allowed to reject the callback if required project state or evidence is missing.

## Safety and diagnostic policy

- The model must select `planner`, `asset`, `logic_coder`, or `unknown`.
- No callback occurs for `unknown` or confidence below `--min-confidence` (default 0.65).
- Harness/integration failures should normally route to `unknown`, not to a game agent.
- Asset and planner callbacks use the actual project modules and may update project files.
- Logic Coder uses the project's existing repair validation, sandbox, smoke gates and rollback logic.
- A failed assertion alone is not proof of root cause. The model receives evidence, requirements, plan architecture and manifest, but it is not given the entire source tree. It should return `unknown` when the evidence is insufficient.
- A Planner rerun requires the original spec file; the code will not invent one.

## Important integration note

This code routes to the existing agent entrypoints and respects their current contracts. It does not guarantee that every runtime observation is sufficient for a correct diagnosis; improving renderer-specific assertions and structured game-state evidence will improve triage quality.
