"""
master_planner/run.py

Orchestrates one full planning pass, end to end:
  1. Calls the Planner (call_planner.run_planner) -> writes plan.json / coder_plan.json.
  2. ALWAYS ensures game/assets/ exists at the project root, regardless of assets.strategy
     — the Coder is told it can rely on that folder existing on every run.
  3. If assets.strategy != "none", feeds the plan's sprites straight into the Asset
     Agent's plan_assets() (no adapter — the schema was changed to match that input
     shape directly), generates with the renderer-appropriate generator, validates,
     and writes asset_manifest.json next to plan.json / coder_plan.json.

Also runs a layout check first: confirms every file/folder this orchestrator depends
on actually exists, before calling anything, so a missing piece fails loudly with a
clear message instead of a confusing stack trace three calls deep.

Run from the project root with:
    python -m master_planner.run
"""

import os
import sys
from pathlib import Path

# Make the project root importable regardless of where this is invoked from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from master_planner.planner.call_planner import run_planner
from master_planner.planner.config.planner_config import GAME_ASSETS_DIR, PLAN_FILE

from master_planner.asset.planner import plan_assets, update_manifest
from master_planner.asset.validator import validate_assets
from master_planner.asset.generator.terminal_generator import generate_terminal_assets
from master_planner.asset.generator.pygame_generator import generate_pygame_assets
from master_planner.asset.generator.godot_generator import generate_godot_assets
from master_planner.asset.generator.image_generation import configure_openrouter, clear_openrouter_config
from master_planner.asset.asset_config import ASSET_IMAGE_MODEL
from config import ASSET_OPENROUTER_API_KEY as OPENROUTER_API_KEY, OPENROUTER_BASE_URL

GENERATORS = {
    "terminal": generate_terminal_assets,
    "pygame": generate_pygame_assets,
    "godot": generate_godot_assets,
}

# Where the asset manifest lands — same folder as plan.json / coder_plan.json,
# so the Coder finds everything it needs in one place.
ASSET_MANIFEST_FILE = PLAN_FILE.parent / "asset_manifest.json"


# ---------------------------------------------------------------------------
# Layout check
# ---------------------------------------------------------------------------

def check_layout() -> list[str]:
    """Confirm every file/folder this orchestrator depends on actually exists.
    Returns a list of problem strings; empty list means the layout is clean."""
    problems = []

    required_files = [
        PROJECT_ROOT / "config.py",
        PROJECT_ROOT / "master_planner" / "planner" / "call_planner.py",
        PROJECT_ROOT / "master_planner" / "planner" / "config" / "planner_config.py",
        PROJECT_ROOT / "master_planner" / "planner" / "resources" / "plan_schema.json",
        PROJECT_ROOT / "master_planner" / "planner" / "resources" / "planner_prompt.txt",
        PROJECT_ROOT / "master_planner" / "asset" / "planner.py",
        PROJECT_ROOT / "master_planner" / "asset" / "validator.py",
        PROJECT_ROOT / "master_planner" / "asset" / "asset_config.py",
        PROJECT_ROOT / "master_planner" / "asset" / "generator" / "image_generation.py",
        PROJECT_ROOT / "master_planner" / "asset" / "generator" / "pygame_generator.py",
        PROJECT_ROOT / "master_planner" / "asset" / "generator" / "terminal_generator.py",
        PROJECT_ROOT / "master_planner" / "asset" / "generator" / "godot_generator.py",
        PROJECT_ROOT / ".env",
    ]
    for f in required_files:
        if not f.is_file():
            problems.append(f"MISSING FILE: {f.relative_to(PROJECT_ROOT)}")

    required_dirs = [
        PROJECT_ROOT / "plans",
        PROJECT_ROOT / "traces",
        PROJECT_ROOT / "game" / "assets",
    ]
    for d in required_dirs:
        if not d.is_dir():
            problems.append(f"MISSING FOLDER: {d.relative_to(PROJECT_ROOT)}")

    # __init__.py markers — missing these makes master_planner.* unimportable as packages.
    required_inits = [
        PROJECT_ROOT / "master_planner" / "planner" / "__init__.py",
        PROJECT_ROOT / "master_planner" / "planner" / "config" / "__init__.py",
        PROJECT_ROOT / "master_planner" / "asset" / "__init__.py",
        PROJECT_ROOT / "master_planner" / "asset" / "generator" / "__init__.py",
    ]
    for f in required_inits:
        if not f.is_file():
            problems.append(f"MISSING __init__.py: {f.relative_to(PROJECT_ROOT)}")

    return problems


# ---------------------------------------------------------------------------
# Asset Agent step
# ---------------------------------------------------------------------------

def run_asset_agent(plan: dict) -> dict | None:
    """
    Feed this plan's architecture.assets straight into the Asset Agent.
    Returns the manifest dict, or None if strategy was "none" (nothing generated).
    """
    arch = plan["architecture"]
    strategy = arch["assets"]["strategy"]
    renderer = plan["profile"]["renderer"]["value"]

    # game/assets/ must exist on EVERY run, strategy "none" included — the Coder
    # was told it can always rely on this folder being there.
    GAME_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    if strategy == "none":
        print(f"[ASSET AGENT] strategy=none — game/assets/ created, nothing to generate.")
        return None

    sprites = arch["assets"].get("sprites", [])
    request = {
        "task_id": plan.get("game_title", "game"),
        "framework": renderer,
        "game_style": plan["profile"]["genre"]["value"],
        # Relative, not GAME_ASSETS_DIR (absolute) — his plan_assets() explicitly
        # rejects an absolute output_dir. Relies on always being run from the
        # project root (python -m master_planner.run), so cwd == PROJECT_ROOT.
        "output_dir": "game/assets",
        # Schema already matches plan_assets()'s expected shape field-for-field
        # (id/type/description/width/height) — only "required" is code-added.
        "assets": [{**sprite, "required": True} for sprite in sprites],
    }

    print(f"[ASSET AGENT] strategy={strategy}, renderer={renderer}, {len(sprites)} sprite(s)")

    planned = plan_assets(request)

    generate = GENERATORS[renderer]
    asset_dir = PROJECT_ROOT / planned["output_dir"]
    generation_results = generate(planned, output_dir=asset_dir)

    validation_results = validate_assets(planned, output_dir=asset_dir)

    manifest = update_manifest(planned, generation_results, validation_results)

    # His generators resolve paths to absolute (their own internal safety check
    # against path traversal) before returning them, and update_manifest() copies
    # that straight through. Convert back to project-relative here so the manifest
    # is portable and doesn't leak a machine-specific absolute path.
    for asset in manifest.get("assets", []):
        if asset.get("path"):
            try:
                asset["path"] = Path(asset["path"]).resolve().relative_to(PROJECT_ROOT).as_posix()
            except ValueError:
                pass  # leave untouched if it's genuinely outside the project root

    ASSET_MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    ASSET_MANIFEST_FILE.write_text(
        __import__("json").dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"[ASSET AGENT] manifest written -> {ASSET_MANIFEST_FILE.relative_to(PROJECT_ROOT)}")
    print(f"[ASSET AGENT] validation passed={manifest['validation']['passed']}")
    for a in manifest.get("assets", []):
        method = a.get("generation_method", "unknown")
        tag = "REAL ART" if method == "genai" else "procedural fallback" if method == "procedural_fallback" else method
        line = f"[ASSET AGENT]   - {a.get('id')}: {tag}"
        if a.get("fallback_reason"):
            line += f" (reason: {a['fallback_reason']})"
        print(line)
    return manifest


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _fake_plan_json() -> str:
    """
    A hand-written, schema-valid plan — used by --dry-run so run_planner()
    never has to call the real model. Deliberately exercises the asset path
    (strategy "ai_art", pygame renderer, 2 sprites of different types) so the
    Asset Agent's full chain (plan_assets -> generate_pygame_assets ->
    validate_assets -> update_manifest) actually runs end to end.
    """
    import json
    return json.dumps({
        "game_title": "Dry Run Game",
        "profile": {
            "genre":      {"value": "top-down adventure", "source": "stated", "quote": "top-down game"},
            "renderer":   {"value": "pygame", "source": "assumed"},
            "dimensions": {"value": "2d", "source": "assumed"},
            "pace":       {"value": "real-time", "source": "assumed"},
            "players":    {"value": 1, "source": "assumed"},
        },
        "requirements": [{
            "text": "Player moves around and collects a key",
            "priority": "core",
            "status": "full",
            "check": "player x or y changes after a key press",
            "milestone": 1,
            "quote": "player moves a character around",
        }],
        "architecture": {
            "entry_point": "game/main.py",
            "files": [
                {"path": "game/__init__.py", "purpose": "package marker"},
                {"path": "game/main.py", "purpose": "whole game"},
            ],
            "dependencies": ["pygame"],
            "assets": {
                "strategy": "ai_art",
                "sprites": [
                    {"id": "player", "type": "sprite", "description": "small adventurer", "width": 64, "height": 64},
                    {"id": "background", "type": "background", "description": "forest clearing", "width": 320, "height": 180},
                ],
            },
            "resolution": {"width": 800, "height": 600},
            "fps": 60,
            "requires_input": True,
            "test_input_example": "hold RIGHT for 30 frames",
            "extensions": {},
        },
        "decisions": [
            {"about": "profile.renderer", "choice": "pygame", "reason": "default; spec names no platform"},
            {"about": "profile.dimensions", "choice": "2d", "reason": "default"},
            {"about": "profile.pace", "choice": "real-time", "reason": "default"},
            {"about": "profile.players", "choice": "1", "reason": "default"},
        ],
        "unmapped": [],
    })


def run(spec: str, dry_run_planner: bool = False, dry_run_assets: bool = False, print_prompt: bool = False) -> dict:
    """
    Full pipeline: Planner -> Asset Agent. Returns the plan dict.

    dry_run_planner: skip the real LLM call, use a scripted plan instead.
    dry_run_assets:  force procedural generation — no OpenRouter image calls,
                     regardless of what assets.strategy the plan (real or fake) picks.
    print_prompt:    print the full rendered system prompt (with {libs}/{art_generation}/
                     {godot}/{schema} substituted) before the first attempt's call.
    These are independent — e.g. real planner call + dry-run assets, to spend
    LLM tokens testing the Planner's own reasoning without spending image credits
    while the asset-side wiring is still being checked.
    """
    problems = check_layout()
    if problems:
        print("=== LAYOUT PROBLEMS — fix these before anything will run correctly ===")
        for p in problems:
            print(f"  - {p}")
        print("=" * 70)
    else:
        print("[LAYOUT] all required files and folders are present.")

    if dry_run_planner:
        print("[DRY RUN] planner: using a scripted plan, no LLM call")
        llm_fn = lambda system, user: _fake_plan_json()
    else:
        llm_fn = None

    if dry_run_assets:
        print("[DRY RUN] assets: forcing procedural generation, no OpenRouter image call")
        os.environ["ASSET_GENERATION_MODE"] = "procedural"
    elif OPENROUTER_API_KEY:
        # Wire the key + model into the image-generation module so
        # generate_image_with_genai() actually has what it needs to call
        # OpenRouter instead of silently falling back to procedural.
        configure_openrouter(OPENROUTER_API_KEY, ASSET_IMAGE_MODEL, OPENROUTER_BASE_URL)
        print(f"[ASSETS] real OpenRouter art generation enabled (model={ASSET_IMAGE_MODEL})")
    else:
        clear_openrouter_config()
        print("[ASSETS] no ASSET_OPENROUTER_API_KEY found — will fall back to procedural generation")

    print("\n=== PLANNER ===")
    plan = run_planner(spec, llm_fn=llm_fn, print_prompt=print_prompt)

    print("\n=== ASSET AGENT ===")
    run_asset_agent(plan)

    return plan


"""if __name__ == "__main__":
    TEST_SPEC = (
        "A simple top-down game where the player moves a character around a "
        "forest with a dungeon entrance, avoiding a slime enemy and collecting "
        "a key to unlock the exit. Include a health pickup."
    )
    planner_dry = "--dry-run" in sys.argv or "--dry-run-planner" in sys.argv
    assets_dry = "--dry-run" in sys.argv or "--dry-run-assets" in sys.argv
    show_prompt = "--show-prompt" in sys.argv
    run(TEST_SPEC, dry_run_planner=planner_dry, dry_run_assets=assets_dry, print_prompt=show_prompt)"""