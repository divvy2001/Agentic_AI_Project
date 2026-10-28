# Eval / Validator handoff contract

English handoff reference for the existing V3/V4 feedback contract and V4.1 shared
debug/Repair design. JSON field names and allowed values are unchanged. This is an
interface description, not a claim that the team's external Validator is implemented.

## Responsibilities

Planner → Asset → Coder Initial Build → Runtime Eval Generator → Validator →
(only an attributed Coder failure) Coder Repair → Validator retest.

Coder implements planned game code and supplies entrypoint/manual/local smoke
evidence. Eval Generator derives versioned tests from the same Plan. Validator
executes real renderer inputs and observations, assigns evidence-based attribution,
and retests. Integration owns routing and overall retry budgets. Coder does not
execute the Validator's authoritative gameplay suite or mark it PASS.

Inputs are the existing `plans/coder_plan.json`, required `plans/asset_manifest.json`,
`game/`, `plans/play_manual.json` and Coder return dictionary. Do not invent another
manifest or change Planner/Asset schemas. `requirements[].check` and the manual's
expected output are test design inputs, not observations.

## Test suite

Generate reproducible actions and assertions with `suite_version`, renderer,
`test_id`, zero-based `requirement_index`, script path and timeout. Bind the version
to script hashes. Reuse the same suite after Repair, including previously passed
tests. An intentional test correction needs a new version and a recorded reason.
Natural-language instructions must not be passed as literal stdin or executable code.
Mark requirements without an observation method as not_testable/inconclusive, not PASS.

## Frozen feedback file

Validator writes `traces/eval/<suite_version>/test_results.json` and its referenced
evidence before invoking `run_repair()`. Paths must be project-relative, use forward
slashes, exist within the project, and must not contain parent traversal or links.
Current Coder accepts suite names containing alphanumeric characters, hyphens or underscores.

Exactly these top-level fields are required:

| Field | Type and rules |
|---|---|
| status | pass, fail, inconclusive |
| failing_stage | planner, asset, logic_coder, runtime_eval_generator, unknown, or null |
| suite_version | Non-empty version string; must match the feedback directory |
| failures | Array; non-empty for fail, empty for pass |
| previously_passed_test_ids | Unique string IDs for subsequent regression checks |

Each failure has exactly these fields:

| Field | Type and rules |
|---|---|
| test_id | Non-empty string; unique, not also listed as passed |
| requirement_index | Zero-based integer within Plan requirements, or null |
| expected / actual | Strings describing observable behavior |
| error_category | spec, asset, behavior, runtime, test_definition, test_infrastructure |
| evidence_path | Existing project-relative evidence file |
| attribution_evidence | Non-empty explanation supporting the failing stage |

```json
{
  "status": "fail",
  "failing_stage": "logic_coder",
  "suite_version": "eval-v1",
  "failures": [{
    "test_id": "T03",
    "requirement_index": 0,
    "expected": "WIN after exactly three scoring actions",
    "actual": "The game remained ONGOING after three scoring actions",
    "error_category": "behavior",
    "evidence_path": "traces/eval/eval-v1/T03.log",
    "attribution_evidence": "Valid input reached the game; its actual output contradicted Plan requirement 0."
  }],
  "previously_passed_test_ids": ["T01"]
}
```

`pass` requires `failing_stage=null`, `failures=[]` and completion of all required
applicable tests. `inconclusive` requires `failing_stage=unknown`; explain missing
evidence. `fail` requires a non-null stage and at least one failure. Use unknown
for mixed/ambiguous attribution. A category alone does not prove the failing stage.

Only `status=fail AND failing_stage=logic_coder` may trigger Repair. Other valid
routes return `blocked(wrong_failing_stage)`; malformed feedback returns
`blocked(invalid_feedback...)`, before model calls or code modification.

## Attribution

- planner: compare original specification and Plan to establish an omission or contradiction.
- asset: establish missing/corrupt required assets or failed upstream generation/validation.
  Correct assets referenced incorrectly by code are a Coder issue.
- logic_coder: verify valid Plan/assets/test actions, then observe a code/runtime/behavior failure.
- runtime_eval_generator: reproduce a wrong assertion, test definition or generated driver.
- unknown: infrastructure failure, undelivered input, unavailable observation or ambiguous cause.

Do not use an unsupported LLM verdict as attribution evidence.

## Renderer observation

Terminal: bounded stdin/stdout interaction, real responses and clean process cleanup.
Pygame: actual events/update path and real state/pixels. Posting KEYDOWN does not
necessarily drive `pygame.key.get_pressed()` as a held physical key.
Godot: real scene loading and Input actions/events, actual node/state/log observations.
`Input.action_press()` does not itself invoke `_input()`; use an appropriate event
path when required. Visual requirements need actual image evidence, not just WIN logs.
No private win-function calls, fabricated event logs or hidden state setters to force success.

## Completion and retest

Internal Self-Debug and external Repair are separate counters in the same Harness.
Repair must patch existing game code and retain Plan/tests/evidence. Local checks
must pass and a real net game change must exist before `ready_for_testing`.
That result asks Validator to retest; it does not certify gameplay.

After Repair, rerun all applicable tests under the same suite version. Require the
original failing tests to pass and previously passed tests not to regress. Preserve
input traces, assertions, stdout/stderr, exit codes and visual evidence where relevant.
SKIPPED, NOT_RUN, TIMEOUT, INFRA_ERROR and inconclusive are never PASS.
