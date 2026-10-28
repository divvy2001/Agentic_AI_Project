# Engineering regression and frozen Repair fixtures

From the package root, in the configured Windows environment:

```powershell
python -B -m unittest discover -s tests_coder -p 'test_*.py' -v
```

The default unittest suite uses deterministic/fake-model tests and native runtime
controls; it is not a paid multi-game benchmark. Required engines must be installed.
Report SKIPPED/NOT_RUN separately. Native windows may open; avoid interacting with them.
Run serially; overlapping native permission/engine activity can cause infrastructure failures.

Frozen fixtures under terminal/, pygame/ and godot/ represent a score-threshold
bug: three scoring actions should WIN (T03); two must not WIN (T01 regression).
Their synthetic Planner-shaped Plans predate the current package-marker rule.
Repair accepts the legacy layout with a warning. Do not use them to certify the
current Planner's full file-contract compliance.

`prepare_repair_workspace.py` copies the current Coder and a frozen fixture to a
new directory, never the real generated game. For example:

```powershell
python tests_coder/prepare_repair_workspace.py --renderer terminal --dest ../terminal-repair-demo
```

Set the Coder key in the new shell's environment before a live Repair; no real
`.env` is copied. The fixture's feedback/evidence are synthetic development inputs.
For real attribution use observations made by the external Validator, as described
in `EVAL_TEST_HANDOFF_CONTRACT.md`. Use public `run_repair()` with launch disabled.
Do not treat an existing synthetic evidence file as a newly observed failure.

The verify_* helpers are historical opt-in acceptance utilities, not the preferred
team workflow and not part of default unittest discovery. Live modes cost money.
The development-only score fixtures are trusted; never host-import arbitrary
model-generated game code when adapting their legacy test scripts.

Current release test counts and limitations are recorded in docs/TEST_STATUS_AND_BASELINE_01.md.
