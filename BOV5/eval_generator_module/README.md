# Bo's Project V4 — Eval Generator module

A standalone, standard-library-only module that creates a **versioned evaluation-suite specification** from the existing Planner output and Coder play manual. It does not modify the Planner, Asset Generator, Coder, or Validator.

## What it does

- Reads `plans/coder_plan.json` and `plans/play_manual.json`.
- Creates one test definition per planned requirement, preserving the zero-based `requirement_index`.
- Supports explicit structured tests in an optional `eval.tests` array in `play_manual.json`.
- Records source hashes, renderer, suite version, test IDs, expected behavior, timeout, and testability status.
- Writes `traces/eval/<suite_version>/suite.json`.
- Refuses to silently overwrite a frozen suite version if the plan/manual inputs changed.
- Does **not** claim tests passed and does **not** write the Validator-owned `test_results.json`.

## Run it

Copy the `eval_generator/` folder into the root of Bo's Project V4, then from the project root run:

```bash
python -m eval_generator.generator --project-root . --suite-version eval-v1
```

If the project uses a different Plan location:

```bash
python -m eval_generator.generator --project-root . --plan plans/coder_plan.json --manual plans/play_manual.json --suite-version eval-v1
```

Output:

```text
traces/eval/eval-v1/suite.json
```

Use a new version such as `eval-v2` if the Plan or manual changes. The generator will not overwrite a suite version created from different source files.

## Optional explicit test definitions

The default `play_manual.json` written by the current Coder contains `test_input`, `expected_win_output`, `expected_lose_output`, and `notes`. These fields are useful context, but they are not enough to safely infer every requirement's exact actions and observation method. The generator deliberately marks those requirements `not_testable` instead of guessing or treating prose as executable input.

To define executable test cases, add an optional `eval` object to `plans/play_manual.json`:

```json
{
  "test_input": "1\\n1\\n1\\n",
  "expected_win_output": "WIN",
  "expected_lose_output": "LOSE",
  "notes": "Example only",
  "eval": {
    "tests": [
      {
        "test_id": "T01",
        "requirement_index": 0,
        "actions": [
          {"type": "stdin", "value": "1\\n"},
          {"type": "stdin", "value": "1\\n"},
          {"type": "stdin", "value": "1\\n"}
        ],
        "observation": {"method": "stdout_contains", "value": "WIN"},
        "expected": "WIN is observed after exactly three valid score actions",
        "timeout_seconds": 10
      }
    ]
  }
}
```

This sample illustrates the schema only; adapt it to the actual game's controls and observable behavior. The current Validator must implement each `actions[].type` and `observation.method` before it can execute the test. `script_path` is optional and only retained if it points to an existing, safe, project-relative file.

## Important boundary: generator vs Validator

This module generates a suite specification, not renderer drivers. A separate Validator still needs to translate actions into real Terminal stdin/stdout, Pygame events/state/pixels, or Godot input/state/screenshots; execute them; capture evidence; and produce the exact contract-compliant file:

`traces/eval/<suite_version>/test_results.json`

Do not pass `suite.json` to `run_repair()` as if it were feedback. Only the Validator's observed results should be passed to Repair. `not_testable`, skipped, timeout, infrastructure error, or missing evidence must never be reported as PASS.

## Test the module

From this folder:

```bash
python -m unittest discover -s tests -v
```
