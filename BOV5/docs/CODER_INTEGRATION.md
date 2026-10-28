# Coder integration and operation

## Architecture

One LLM tool-calling Agent, one bounded Harness, two public entrypoints.
Initial Build consumes the Planner's existing Plan and asset products. Repair
consumes the same Plan, existing game and externally attributed Validator failures.
Both use `read_plan`, `list_assets`, `read_file`, `write_file`, `apply_patch`,
`run_shell`, and `write_play_manual`. No second Repair Agent is introduced.

| Source | Responsibility |
|---|---|
| initial_build.py / repair.py | Independent public modes; feedback routing and validation |
| agent_coder.py | Model/tool loop, budgets, local debugging, completion and usage |
| context.py / build_brief.py | Mode instructions, compact context and implementation brief |
| contracts.py / workspace.py | Planner contracts, asset ownership, old-game backup and workspace preparation |
| tools/ | Confined reads, atomic writes, batch patches and fixed commands |
| adapters/ | Renderer playbooks and renderer-specific source/boot checks |
| gates.py / presentation.py | File, syntax/import, bounded boot and presentation checks |
| python_runtime.py / godot_runtime.py / windows_sandbox.py | Credential-free disposable native execution |
| run_context.py / build_state.py | Lock, snapshots, file versions and durable checkpoints |
| diagnostics.py | Local error and external-feedback context |
| launch_game.py / play_host.py / play_child.py | Separate manual play session after successful delivery |

## Public calls

Run from the project root with a valid `plans/coder_plan.json` and required assets:

```python
from coder_agent_adhoc.initial_build import run_initial_build
result = run_initial_build(dry_run=False, launch_game=False)

# The external Validator writes this file and its evidence first.
from coder_agent_adhoc.repair import run_repair
result = run_repair('traces/eval/eval-v1/test_results.json',
                    dry_run=False, launch_game=False)
```

```powershell
python -m coder_agent_adhoc.initial_build --no-launch
python -m coder_agent_adhoc.repair --feedback traces/eval/eval-v1/test_results.json --no-launch
python -m coder_agent_adhoc.launch_game
```

Treat `blocked` and `budget_exhausted` as incomplete delivery. Route by `reason`;
do not repeatedly invoke paid trials or mislabel an infrastructure failure as a
gameplay failure. The returned `usage`, `changes`, `debug_statistics`, `smoke`,
`reason`, `file_inventory` and trace paths are available for integration.
Model coverage is an unverified claim; it is not a test result.

## Initial Build, backup and assets

The Plan remains authoritative for renderer, entrypoint, file list, requirements
and asset strategy. New Build requires `game/__init__.py` first in the planned list.
Godot additionally needs the specified scene/scripts and `game/project.godot`.
An existing game is backed up under `backups/`; the current task is generated under
`game/`. Only assets recognized by the current Plan/manifest and protected tests
are retained. Unknown or stale assets go into the old-game backup. Asset provenance
is limited by metadata supplied upstream; identical task titles are not strong provenance.

Repair does not clear the existing game or rerun Planner/Asset. It reads current
code, prefers incremental `apply_patch`, protects Plan/tests/evidence/assets, and
requires a real net game change before completion. Failed Repair attempts restore
their own writes when safe; conflicting external changes require review of the snapshot.

## Resume is not Repair

```powershell
python -m coder_agent_adhoc.initial_build --resume ATTEMPT_ID --dry-run --no-launch
python -m coder_agent_adhoc.initial_build --resume ATTEMPT_ID --no-launch
```

Resume preserves the same attempt's calls, tokens, known cost and elapsed time.
Checkpoints live in `traces/build_state/`. Input/source hash conflicts block resume.
An in-flight request or unknown billed outcome must be audited before replay;
there is no general operator billing-unlock utility in this package.

## Configuration

The tested defaults are model `google/gemini-2.5-flash`, 40 steps, 1800 seconds,
450000 cumulative input/output tokens, and 16384 maximum output tokens per call.
These limits exceed Baseline 01 and prevent a fair unadjusted performance comparison.

Environment overrides include `CODER_MODEL`, `CODER_MAX_STEPS`, `CODER_MAX_SECONDS`,
`CODER_MAX_TOKENS`, `CODER_MODEL_MAX_OUTPUT_TOKENS`, `CODER_MAX_COST_USD`,
`CODER_COMMAND_TIMEOUT`, `CODER_OUTPUT_LIMIT`, `CODER_RECENT_TURNS`,
`CODER_STAGNATION_LIMIT`, `CODER_REPEATED_TOOL_FAILURE_LIMIT`,
`CODER_PHASE_CHECK_INTERVAL`, `CODER_MODEL_TIMEOUT`,
`CODER_PROVIDER_RETRIES_PER_FAILURE`, and `CODER_PROVIDER_RETRIES_TOTAL`.
Cost is unknown when the provider omits it. Application budgets are not account-side
hard caps. SDK implicit retries are disabled; bounded explicit retries remain logged.

## Evidence and launch

Read `traces/coder_attempts.jsonl`, `traces/coder_result.json` (when emitted),
`plans/play_manual.json` and renderer logs. Early preflight blocks may not produce
a delivery receipt. Never assume a receipt from a previous task belongs to the new task.
The launcher validates existing output and rejects a matching failed receipt.
Direct Godot execution bypasses this guard.

Godot: `& $env:GODOT_BINARY --path game` after setting the environment variable,
or open `game/project.godot` in Godot and run the project (F6 runs only a scene).
Pygame/Terminal: use the Plan's actual Python entrypoint, typically `python game/main.py`.

Presentation checks catch selected empty-frame/camera/load failures, not complete
visual correctness. Production Godot boot currently also performs bounded pointer
exploration; it can skip all controls. This is a known boundary deviation from the
original startup-only design and is not an authoritative gameplay test. Move input
driving to external eval in a subsequent scoped change; this package preserves the
current source and discloses the limitation instead of silently changing behavior.
