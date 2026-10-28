# PE6203 Logic Coder — integration handoff

Release date: 2026-10-26 (Asia/Shanghai). Status: integration candidate, not a new frozen baseline.

This package contains the existing Planner and Asset pipeline plus the current Logic Coder.
Planner and Asset source bytes are unchanged. The temporary Coder is replaced by
`coder_agent_adhoc/`. Initial Build and external-feedback Repair share one bounded
LangChain/OpenRouter tool-calling loop and seven tools.

## Read these files

| Document | Purpose |
|---|---|
| README.md | Environment, keys, first run, package contents |
| docs/CODER_INTEGRATION.md | Build/Repair entrypoints, architecture, budgets, resume and launch |
| EVAL_TEST_HANDOFF_CONTRACT.md | English description of the existing Validator feedback contract; fields unchanged |
| docs/TEST_STATUS_AND_BASELINE_01.md | Actual evidence, Baseline 01 comparison and unresolved issues |
| docs/MANUAL_TESTS.md | Three manual end-to-end cases, including generated assets |
| tests_coder/README.md | Offline engineering regression and fixture usage |

## Setup (Windows)

Extract to a writable folder and open PowerShell in this folder. Python 3.11 is
the tested interpreter; the Planner requires Python 3.10 or newer. Production
native checks currently require Windows AppContainer. No unsandboxed fallback is provided.

```powershell
conda env create -f environment.yml
conda activate pe6203-logic-coder
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally. Supply independent `PLANNER_OPENROUTER_API_KEY`,
`ASSET_OPENROUTER_API_KEY`, and `CODER_OPENROUTER_API_KEY` values. Do not share `.env`.
For Godot, install a Godot 4 executable and set `GODOT_BINARY` to its absolute path,
for example `C:/Tools/Godot/Godot_v4.7.2-stable_win64.exe`.
Godot 4.7.2 was used for the recorded native checks; the engine binary is not bundled.

The pinned dependencies reflect the developer environment. A clean Conda install
on another machine has not been certified; report installation failures separately
from game failures. This archive contains no API key or environment directory.

## Run a full pipeline

Open `test.py`, replace `SPEC`, and review its flags before running:

```powershell
python test.py
```

The shipped configuration enables real Planner, Asset and Coder calls; this costs money.
Set `DRY_RUN_ASSETS=True` for procedural fallback when appropriate; do not use that
setting to claim an AI-art test passed. `DRY_RUN_PLANNER=True` uses a scripted plan
and ignores the requested game specification. `CODER_DRY_RUN=True` does not generate a game.
The source sample prompt is in English; it is a starting input, not a passed delivery.

Inspect `plans/coder_plan.json` before accepting a result: confirm renderer,
requirements, promised files and asset strategy. On Planner truncation or fallback,
the original request may no longer be represented. Do not report the fallback game
as fulfilling the original specification.

Successful Build/Repair opens a play session by default. Automation must pass
`launch_game=False` or `--no-launch`. `ready_for_testing` is not gameplay PASS.

## Included / excluded

Included: runtime source, Planner schema/prompts, current Coder prompts/playbooks,
tests and frozen engineering fixtures, empty runtime folders, English handoff docs,
selected evidence and integrity manifests.
Excluded: credentials, old generated games/assets/plans, caches, backups, IDE files,
virtual environments, engine executable, historical ZIPs and the full research eval workspace.
The old generated game was intentionally not selected as a reference game.

`evidence/terminal_repair/` preserves a real external test → Repair → same-test
retest. The developer's `evaluation.simple_validator` runner and Baseline 01 archive
are not runtime dependencies and are not included in this integration package.
Use the frozen fixtures for development and connect the team's Validator through
the unchanged contract for real game acceptance.

`MANIFEST.sha256.json` hashes every packaged file except itself. `PACKAGING_AUDIT.json`
records byte equality against source and package checks. Original archived evidence
can contain historical absolute paths; those are provenance, not required runtime paths.
