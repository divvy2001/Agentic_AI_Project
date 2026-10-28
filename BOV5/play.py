"""
play.py: play the game the pipeline just built (pygame or Godot).

Press Run in VS Code on this file, or:  python play.py
It reads plans/coder_plan.json to find the engine and entry point, so you never
have to remember `python -m game.xxx` or the Godot command.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)


def load_env():
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()
    plan_file = ROOT / "plans" / "coder_plan.json"
    if not plan_file.is_file():
        sys.exit("No plans/coder_plan.json yet: run run_pipeline.py first.")
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    renderer = plan["profile"]["renderer"]
    renderer = renderer if isinstance(renderer, str) else renderer.get("value")
    entry = plan["architecture"]["entry_point"]
    print(f"Playing: {plan.get('game_title', 'game')}  ({renderer}, {entry})")

    if renderer == "godot":
        godot = os.getenv("GODOT_BINARY") or "godot"
        # import images first so sprites load, then open the game window
        subprocess.run([godot, "--headless", "--path", "game", "--import"], cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cmd = [godot, "--path", "game"]
    else:
        module = entry[:-3].replace("/", ".") if entry.endswith(".py") else entry
        cmd = [sys.executable, "-m", module]
    sys.exit(subprocess.call(cmd, cwd=ROOT))


if __name__ == "__main__":
    main()
