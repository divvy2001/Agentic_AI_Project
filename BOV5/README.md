# Game Jam Agent: install and run guide

A multi-agent pipeline that turns a written game spec into a playable game, then tests its controls.

```
game spec (.md) -> Planner -> Asset Agent -> Logic Coder -> Eval Generator -> Runtime Tester -> result
                                                                                   |
                                     (optional) Triage Agent routes failures back to Planner / Asset / Coder
```

| Agent | Folder | What it does |
|---|---|---|
| Planner | `master_planner/planner/` | Spec -> structured plan: engine (pygame / Godot / terminal), requirements, files, assets |
| Asset Agent | `master_planner/asset/` | Generates the planned images with AI (or plain shapes in dry-run mode) |
| Logic Coder | `coder_agent_adhoc/` | Tool-using agent that writes the game and checks it builds and boots |
| Eval Generator | `eval_generator_module/` | Finds the game's controls in the play manual and writes one test per control |
| Runtime Tester | `bo_v4_tester_v1/` | Launches the game, presses each key / types each command, checks the printed line |
| Triage Agent | `triage_agent/` | Diagnoses failures and routes the fix |
| Orchestrator | `run_pipeline.py` | Runs everything above in order, meters cost, writes traces, review and gallery copy |

---

## 1. Folder layout

Keep these three folders side by side:

```
<your working folder>\
  BOV5\                  <- this project
  game_specs\            <- one .md file per game spec
  Game that it makes\    <- gallery of finished games (created automatically)
     Pygame\  Godot\  Terminal\
```

**Location matters (Windows sandbox):** put the project under your own user folder (not a shared or
root location). Avoid OneDrive folders, other drives (e.g. D:) and the root of the C: drive, which
caused permission errors before.

---

## 2. Requirements

| Need | Version | Notes |
|---|---|---|
| Windows | 10 / 11 | The coder's checks run in a Windows AppContainer sandbox |
| Python | 3.11 (3.10+) | Install from python.org. Use the normal install, **not a venv** (the sandbox can't use venv launchers) |
| Godot | 4.x (tested 4.7.2) | Only for Godot games. Download the `win64` exe; no install needed |
| OpenRouter account | with credit | Each run costs about $0.03 – $0.30 |

---

## 3. Install

Open **PowerShell** or **Command Prompt** in the `BOV5` folder:

```powershell
python -m pip install -r requirements.txt
python -m pip install pyautogui
```

`pyautogui` is needed by the Tester to press keys in game windows.

If you previously installed the `langchain` package (1.x), remove it; it clashes with the pinned version:

```powershell
python -m pip uninstall langchain
```

---

## 4. Configure `.env`

Create a file named `.env` in the `BOV5` folder (never share it; it holds your keys):

```dotenv
# --- API keys (OpenRouter, start with sk-or-) ---
PLANNER_OPENROUTER_API_KEY=sk-or-...
ASSET_OPENROUTER_API_KEY=sk-or-...
CODER_OPENROUTER_API_KEY=sk-or-...

# --- Godot (only for Godot games) ---
GODOT_BINARY=C:\Users\<you>\Tools\Godot_v4.7.2-stable_win64.exe

# --- Coder settings that worked well ---
CODER_MODEL=openai/gpt-5-mini
CODER_MAX_STEPS=80
CODER_MAX_TOKENS=1500000
CODER_MAX_SECONDS=3600
CODER_MAX_COST_USD=1.00
CODER_COMMAND_TIMEOUT=120
```

The three keys can be the same key. Set a credit limit on the key in OpenRouter as a safety net.

---

## 5. Check the setup (free)

```powershell
python preflight.py        # checks Python, packages, imports, .env keys, key credit, Godot, coder config
python credit_check.py     # shows how much credit each key has left
```

Fix every `FAIL` line before running.

---

## 6. Write or pick a game spec

Specs live in `..\game_specs\`, one `.md` file per game. **Only the text under `## Spec` is sent to the Planner**;
the title and `## Notes` are for you (e.g. the engine you expect), so you can keep notes without hinting the Planner.

```markdown
# Game Title

## Spec

Describe the game in plain English: what it is, how it's played, and what it must do. Print a line to the
console every time a control takes effect, e.g. MOVE LEFT, MOVE RIGHT, RESTART and QUIT.

## Notes

- Expected engine: pygame / Godot / terminal (optional — the Planner picks one if you leave this out)
```

**For the tests to work, every spec should say which line each control prints** (e.g.
`MOVE LEFT`, `RESTART`, `QUIT`). The Tester checks controls by those printed lines.

Included specs: `snake`, `block_dodge`, `kitty_catch`, `apple_basket`, `crumb_chase_pygame`, `dojo_duel_pygame`,
`star_courier`, `tower_tiles`, `dungeon_delve`, `sky_ladder`, `blast_grid` (pygame); `bounce_keeper`,
`moon_hopper`, `seal_bounce`, `crumb_chase_godot`, `dojo_duel_godot` (Godot); `lantern_cave` (terminal).

---

## 7. Run the pipeline

```powershell
python run_pipeline.py                 # builds SPEC_FILE set in run_pipeline.py
python run_pipeline.py kitty_catch     # or pick a spec by name (with or without .md)
```

**While it runs:**

- Close the **Godot editor** and any window showing the `game` folder (they lock the folder).
- In VS Code, turn off **File > Auto Save** and don't save `run_pipeline.py` or agent files while a run is going.
- **Don't touch the keyboard or mouse during the Tester stage**: it presses keys in the game window.

### Settings (top of `run_pipeline.py`)

| Group | Setting | Default | Meaning |
|---|---|---|---|
| Spec | `SPEC_FILE` | `lantern_cave.md`[^1] | which spec to build (overridden by the command-line name) |
| Asset Agent | `DRY_RUN_ASSETS` | `False` | `True` = plain shapes, no paid images |
| Tester | `STARTUP_WAIT` | `2.0` | seconds before the first key press |
| Tester | `TESTER_LIMIT` | `0` | run only the first N tests (0 = all) |
| Triage | `USE_TRIAGE` | `True` | `True` = route failures to Planner / Asset / Coder and retest |
| Triage | `MAX_ROUNDS`, `TRIAGE_MIN_CONFIDENCE` | `3`, `0.65` | repair rounds and confidence gate (only when triage is on) |
| Stop | `DONE_IF_ANY_PASS` | `False` | stop at the first passing test |
| Outputs | `TRACK_COST` | `True` | measure cost per agent |
| Outputs | `EXPORT_REVIEW` | `True` | write `game\_review\` and a zip in `exports\` |
| Outputs | `COPY_TO_GALLERY` | `True` | copy finished games to the gallery |
| Outputs | `FINAL_BOOT_SECONDS` | `6` | run the finished game headless this long and save its output |

[^1]: Updated from `tower_tiles.md` to match the current default in `run_pipeline.py`.

---

## 8. What you get

| Where | What |
|---|---|
| Console | each stage, every coder step (`[CODER] step N ...`), cost per agent, routing, final result |
| `game\` | the built game |
| `game\_review\README.md` | one-page summary: spec, agent table, control test results |
| `game\_review\DEBUG_TURNS.md` | every coder step and Tester action, plus a loop analysis (where steps were wasted) |
| `game\_review\CHECK_OUTPUT.md` / `FINAL_BOOT.md` | full engine errors from the coder's checks / the finished game's own output |
| `game\_review\HUMAN_CHECK.md` | fill in after playing; ground truth for the automated result |
| `game\_review\metrics.json`, `settings.json` | all numbers per agent; models, limits, versions used |
| `exports\<run>_<title>.zip` | game + review in one file |
| `..\Game that it makes\<Engine>\<Title>\` | gallery copy with `play.bat` and `GAME_INFO.md` |
| `runs_index.csv` | one row per run (engine, steps, cost, tests passed, top error, human verdict) |
| `traces\` | raw traces: `pipeline\<run>\`, `eval\<suite>\`, `coder_attempts.jsonl`, `planner_attempts.jsonl` |

**Result line:**

- `GAME READY`: all control tests passed
- `DONE: X passed, Y failed`: tests ran, some failed (see `DEBUG_TURNS.md` section 3)
- `STOPPED: coder did not finish`: see `DEBUG_TURNS.md` section 4 for where the steps went

---

## 9. Play a game

```powershell
python play.py                  # plays the game currently in BOV5\game (pygame, Godot or terminal)
```

Or double-click **`play.bat`** in the game's gallery folder.

Pygame games must be started as a module from the folder **above** `game\`
(`python -m game.<entry>`); `play.py` and `play.bat` do this for you.
Running `main.py` directly gives `No module named 'game'`.

---

## 10. Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `402 insufficient credits` | key out of credit / over its limit | top up or raise the key limit; run `credit_check.py` |
| `resume_billing_audit_required` | resuming after a billing error | run fresh (no `--resume`) |
| `workspace_recovery_required` | `game\` was locked during the swap (Godot editor / Explorer open) | close them; inspect `traces\workspace_swap.json`; if `game\` is intact, set its `state` to `rolled_back` |
| `sandbox_acl_failed` / `Permission denied` | project in OneDrive, D: or C:\ root | move to `C:\Users\<you>\Work\BOV5` |
| `module 'langchain' has no attribute 'verbose'` | stray `langchain` package | `python -m pip uninstall langchain` |
| `No Python at ...` | running from a venv | use the normal Python install (`deactivate`) |
| `budget_exhausted` | coder hit its step / token limit | simplify the spec, or raise `CODER_MAX_STEPS` |
| Tests fail but the game plays fine | keys not reaching the window | don't touch keyboard/mouse during testing; check `window_focused` in `DEBUG_TURNS.md` |
| Your edits / my fixes disappear | VS Code Auto Save overwrote the file | turn off Auto Save; use *File: Revert File* |

---

## 11. Scope and known limits

- **Tests cover controls only**: each key/command must print its line. Game mechanics and playability are not
  tested automatically (see `HUMAN_CHECK.md`).
- **Triage is on by default** (`USE_TRIAGE = True`): failed tests are routed back to Planner / Asset / Coder
  and retested, up to `MAX_ROUNDS`. Set `USE_TRIAGE = False` to test once and stop instead.
- **Godot builds cost ~5–10x more coder steps than pygame**; specs that mention visual editors or full animation
  sets often run out of steps.

---

## Appendix: package handoff notes

The notes below describe a specific integration handoff of this package (release 2026-10-26, Asia/Shanghai) and
are kept for provenance; they may not reflect the current state of every file.

### Related documents

| Document | Purpose |
|---|---|
| README.md | Environment, keys, first run, package contents (this file) |
| docs/CODER_INTEGRATION.md | Build/Repair entrypoints, architecture, budgets, resume and launch |
| EVAL_TEST_HANDOFF_CONTRACT.md | English description of the existing Validator feedback contract; fields unchanged |
| docs/TEST_STATUS_AND_BASELINE_01.md | Actual evidence, Baseline 01 comparison and unresolved issues |
| docs/MANUAL_TESTS.md | Three manual end-to-end cases, including generated assets |
| tests_coder/README.md | Offline engineering regression and fixture usage |

### Included / excluded in that handoff

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
