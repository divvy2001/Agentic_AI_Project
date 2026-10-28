# Manual end-to-end tests

Run one task at a time. Put the selected English prompt in `test.py` SPEC, use real
Planner/Coder flags, and decide explicitly whether real Asset calls are enabled.
Do not run the next Build until the current play session is closed and evidence saved.
Check the Plan's renderer, file list, requirements and asset strategy before judging output.
Record actual observations; these prompts are not claims of passing results.

## 1. Terminal — Monster Trio

> Create a turn-based Terminal monster battle game. Let the player choose one of three
> monsters with distinct HP, attack and a limited-use special move. Each turn offers
> attack, defend and special. The opponent chooses a legal action. Show actual HP and
> remaining special uses after every turn. Invalid input must not consume a turn.
> End with WIN or LOSE, prevent actions after the outcome, offer a replay with fresh
> state, and allow quitting. Handle EOF gracefully. Use no external assets.

Check all choices, special exhaustion, defend behavior, invalid input, both outcomes,
replay and quit. The exact balancing must follow the resulting Plan. Start with the
planned Python entrypoint. A script waiting for valid stdin is not automatically broken.

## 2. Pygame with assets — Pixel Pet Garden

> Create a small top-down 2D Pygame game called Pixel Pet Garden. Generate separate
> character, pet, apple and garden background image assets. Do not require manual
> downloads. Use WASD and arrow keys for movement within the garden. Collect three
> apples; each apple disappears once. Approach the pet and press E to feed it only
> after collecting all three. Show a counter, controls and a visible happy reaction
> with WIN. Freeze movement after winning. R resets all objects and state, Escape quits.

Set `DRY_RUN_ASSETS=False` and configure the Asset key. Confirm the Plan requests
ai_art and the manifest records actual files. Verify those images are displayed,
transparency/scale/readability, both movement schemes, early feeding rejection,
single collection, WIN freeze and at least three resets without duplicates.
Asset fallback is a different test outcome; report it explicitly.

## 3. Godot 3D — Energy Extraction

> Create a genuine Godot 4 3D arena game using procedural meshes and no external
> assets. Use a CharacterBody3D player and fixed elevated Camera3D. WASD and arrows
> move with frame-rate-independent speed. Three energy orbs unlock a green exit;
> a red hazard causes LOSE. Show orb count, controls and status in a CanvasLayer HUD.
> Use a reusable orb scene and script. WIN/LOSE freeze movement. R resets everything
> without duplicate nodes or stale references; Escape quits.

Confirm the Plan selects Godot/3D. Open `game/project.godot` and run the whole project.
Check the visible floor/player/orbs/exit/hazard, both movement schemes, locked exit,
all collections, separate WIN and LOSE paths, frozen movement, repeated resets and quit.
Inspect script errors even if the process exits 0. Node frames alone do not prove input works.

## External Repair for a real game

Keep the original Plan and existing game. Validator records reproducible actual
failure evidence using the root feedback contract; submit only attributed Coder
failures through `run_repair(..., launch_game=False)`. Then rerun the same tests,
including previously passed behavior. Do not rewrite rules or assertions to make PASS.

For each attempt save: original prompt, Plan, asset manifest/files, Coder result,
trace/usage, manual observations, Validator feedback, patch and same-suite retest.
Separate engine startup, functional behavior, visuals, missing observations and provider failures.
