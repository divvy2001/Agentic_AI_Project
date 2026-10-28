"""Stage a synthetic failing game in a NEW isolated directory; never alter real game/.

Usage: python tests_coder/prepare_repair_workspace.py --renderer terminal --dest /tmp/repair_terminal
Then: cd /tmp/repair_terminal
      python -c "from coder_agent_adhoc.agent_coder import run_coder; print(run_coder(mode='repair', feedback_path='traces/eval/eval-v1/test_results.json'))"
Only run that last command after Codex implements Repair and a Coder key is provided.
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def prepare(renderer, destination):
    fixture = FIXTURES / renderer
    if not fixture.is_dir():
        raise ValueError(f"Unknown fixture renderer: {renderer}")
    dest = destination.resolve()
    if dest.exists():
        raise FileExistsError(f"Destination already exists: {dest} (will not overwrite)")
    dest.mkdir(parents=True)
    shutil.copytree(ROOT / "coder_agent_adhoc", dest / "coder_agent_adhoc",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "config.py", dest / "config.py")
    (dest / "plans").mkdir()
    shutil.copy2(fixture / "coder_plan.json", dest / "plans" / "coder_plan.json")
    shutil.copytree(fixture / "game", dest / "game")
    # Never copy actual game or existing credentials; all contents come from fixture.
    target = dest / "traces/eval/eval-v1"
    target.mkdir(parents=True)
    shutil.copy2(fixture / "feedback.json", target / "test_results.json")
    shutil.copy2(fixture / "traces/eval/eval-v1/T03.log", target / "T03.log")
    if (fixture / "tests").is_dir():
        shutil.copytree(fixture / "tests", dest / "eval_tests")
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--renderer", required=True, choices=("terminal", "pygame", "godot"))
    parser.add_argument("--dest", required=True, type=Path)
    args = parser.parse_args()
    dest = prepare(args.renderer, args.dest)
    print("Isolated repair workspace:", dest)
    print("Feedback:", dest / "traces/eval/eval-v1/test_results.json")
    print("Run the fixture's frozen behavior/regression tests before & after Coder Repair.")
