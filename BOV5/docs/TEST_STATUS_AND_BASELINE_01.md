# Test status and comparison with Baseline 01

Release: 2026-10-26, integration candidate. No baseline promotion and no new paid
model trial during packaging. Preserve PASS/FAIL/NOT_RUN distinctions.

## Evidence included

| Evidence | Observation | Scope |
|---|---|---|
| evidence/current_regression.log | 153 tests, PASS, 346.132 seconds; see full log for failures/skips | Current source engineering regression, not generated-game success rate |
| evidence/baseline_01_regression.log | Historical 77 tests passed, zero failed/skipped; 207.373 seconds | Frozen Baseline 01 suite, executed 2026-10-24; not rerun for this archive |
| evidence/terminal_repair/summary.json | Real Terminal Repair PASS; T03 FAIL→PASS, T01 PASS→PASS | One minimal threshold fixture; external same-suite retest |
| evidence/terminal_repair/negative.json | Seven invalid/non-Coder feedback routes blocked | No model initialization or workspace mutation |
| evidence/terminal_repair/repair.diff | `score > 3` changed to `score >= 3` | One incremental game-source patch |
| evidence/actual_input_controls_serial.log | Eight targeted checks passed on their recorded source version | Historical infrastructure/native controls; not a new live gameplay score |
| evidence/latest_native_boot.json | 600 simulated frames, but zero button attempts/presses and zero world points | Counterexample: boot can pass without interaction coverage |

The real Terminal Repair used four model requests, 15472 input tokens and 448 output
tokens. Provider responses reported USD 0.00327841, with no missing response cost.
Generation-account metadata was not independently queried for that trial; do not
describe the reported amount as independently audited billing.
The parent summary's external `after` results establish the retest. The nested
Coder `requirement_coverage[].validator_status=not_run` was emitted before external
retest and intentionally remains separate from authoritative test observations.

The demo is a legacy, synthetic score counter. It is not an unseen game, not a
full Planner-to-game acceptance run, and not an estimate of general Repair success.
Pygame/Godot live Repair were NOT RUN in this latest demo batch.

## Baseline 01 versus current implementation

| Dimension | Baseline 01 | Current source |
|---|---|---|
| Agent architecture | Single LangChain/OpenRouter loop, independent modes, seven tools | Same architecture retained; no new Repair Agent |
| Context | Full accumulated message history | Compact recent turns, bounded read/evidence context and file/interface summaries |
| Editing | Basic file read/patch | Line ranges, atomic multi-edit patch, CRLF preservation, stale-read protection |
| Existing assets | Broadly preserves assets/tests | Recognizes current Plan/manifest assets; backs up stale/unrecognized files |
| Completion | Local smoke gates and model completion | Net-change checks, integration checks, explicit readiness/coverage distinction |
| Recovery | Trace/snapshots, limited interruption recovery | Durable same-attempt Build resume, inherited budgets and hash conflict checks |
| Godot delivery | Basic scene/engine startup observation | More resource/TSCN checks, actual presentation and delayed native controls |
| Default budget | 25 steps, 180000 cumulative tokens | 40 steps, 450000 cumulative tokens; environment overrides |
| Offline regression evidence | Historical 77-test suite | 153 tests, PASS, 346.132 seconds; see full log for failures/skips; expanded suite, not a matched performance experiment |
| First-build success/cost advantage | No formal estimate | No matched repeated experiment; no percentage advantage established |

These are source-level and scoped evidence differences. More tests and larger
budgets do not demonstrate greater first-build success. A fair comparison requires
the same frozen prompts/Plans/assets, environment, model/provider, output limits,
total budgets, retries, scoring and repeated runs on both versions. Use fresh
Build workspaces; evaluate Repair separately on identical faulty game snapshots.
Do not compare an old first attempt with a current multi-resume output.

Baseline 01 remains unchanged in the developer workspace and is not copied into
this runtime archive. Its original evidence and manifest remain the reference.
The package source manifest identifies this candidate without renaming it baseline 02.

## Material unresolved issues

1. No formal repeated same-budget Baseline 01/current comparison or holdout success rate.
2. Complex Godot game delivery is not reliably established. A prior plant-defense
   development output showed missing board presentation, ineffective planting and
   failed reset after LOSE. It is excluded from this archive; no claim of its repair.
3. Godot startup input exploration can skip every control and still accept bounded
   boot. Frames/zero errors do not establish movement, UI actions, WIN/LOSE or reset.
4. Bounded production gameplay input exploration exceeds the original startup-only
   Coder boundary; moving it to external eval remains a follow-up scope decision.
5. Full visual quality, physical keyboard play, unseen 3D games and complete
   natural win/loss paths are not certified by the included engineering tests.
6. Latest runtime supports Windows AppContainer; native Linux/macOS support is absent.
7. Planner output can exceed its unchanged 8000-token cap and fall back to a degraded
   Plan, including a different renderer. Planner failure usage may be omitted from
   its final summary. Inspect real attempts; this packaging does not modify upstream.
8. A configured Asset key does not prove image generation/validation succeeded.
   Prior assets also showed transparency limitations. Inspect actual manifest/files.
9. Provider errors, location restrictions, missing responses and unknown billing can
   block delivery. Do not automatically replay an in-flight paid request.
10. New-machine Conda installation and end-to-end live game generation from this
    clean archive are NOT RUN. Archive integrity/offline packaging checks are separate.

## Team acceptance recommendation

Use this candidate for integration. Verify the Plan first, then real launch,
functional behavior, assets/visuals and same-suite external Repair regression on
Terminal, Pygame and Godot. Keep missing observations explicit. Mark a release
accepted only when the applicable requirements have independent evidence.
