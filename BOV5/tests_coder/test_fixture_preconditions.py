"""Offline fixture preconditions: T03 must FAIL and T01 must PASS before repair.

These preconditions alone do not constitute a Repair acceptance test.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def safe_environment():
    return {k: os.environ[k] for k in (
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "USERPROFILE"
    ) if k in os.environ}


def run_python_fixture(renderer, which):
    root = FIXTURES / renderer
    script = root / "tests" / f"test_{which}.py"
    return subprocess.run(
        [sys.executable, str(script)], cwd=root,
        capture_output=True, text=True, timeout=10, env=safe_environment(),
    )


class FixturePreconditions(unittest.TestCase):
    def test_terminal_bug_pre_exists(self):
        r = run_python_fixture("terminal", "behavior")
        self.assertNotEqual(r.returncode, 0, "Fixture accidentally already works")
        self.assertIn("SCORE:3 STATUS:ONGOING", r.stdout + r.stderr)

    def test_terminal_regression_still_passes(self):
        r = run_python_fixture("terminal", "regression")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_pygame_bug_pre_exists_using_game_state(self):
        r = run_python_fixture("pygame", "behavior")
        self.assertNotEqual(r.returncode, 0, "Fixture accidentally already works")
        self.assertIn("phase=PLAYING", r.stdout + r.stderr)

    def test_pygame_regression_still_passes(self):
        r = run_python_fixture("pygame", "regression")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_pygame_real_engine_boot(self):
        try:
            import pygame  # noqa: F401
        except ImportError:
            self.skipTest("pygame runtime not installed (not counted as pass)")
        root = FIXTURES / "pygame"
        env = safe_environment()
        env["SDL_VIDEODRIVER"] = "dummy"
        env["SDL_AUDIODRIVER"] = "dummy"
        env["CODER_SMOKE_FRAMES"] = "5"
        for k in ("OPENROUTER_API_KEY", "PLANNER_OPENROUTER_API_KEY", "ASSET_OPENROUTER_API_KEY", "CODER_OPENROUTER_API_KEY"):
            env.pop(k, None)
        r = subprocess.run([sys.executable, "-m", "game.main"], cwd=root, env=env,
                           capture_output=True, text=True, timeout=12)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_godot_real_scene_bug_and_regression(self):
        godot = os.environ.get("GODOT_BINARY") or shutil.which("godot") or shutil.which("godot4")
        if not godot:
            self.skipTest("Godot binary not installed (not counted as pass)")
        root = FIXTURES / "godot" / "game"
        for name, expect_pass in (("test_behavior", False), ("test_regression", True)):
            cmd = [str(godot), "--headless", "--path", str(root), "--script", f"res://tests/{name}.gd"]
            r = subprocess.run(cmd, cwd=root, env=safe_environment(), capture_output=True, text=True, timeout=20)
            if expect_pass:
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            else:
                self.assertNotEqual(r.returncode, 0, "Godot fixture unexpectedly passed the known bug test")
                self.assertIn("T03 failed", r.stdout + r.stderr)

    def test_all_feedback_fixtures_use_frozen_eval_contract(self):
        allowed = {"planner", "asset", "logic_coder", "runtime_eval_generator", "unknown"}
        for renderer in ("terminal", "pygame", "godot"):
            with self.subTest(renderer=renderer):
                root = FIXTURES / renderer
                fb = json.loads((root / "feedback.json").read_text(encoding="utf-8"))
                self.assertEqual(fb["status"], "fail")
                self.assertIn(fb["failing_stage"], allowed)
                self.assertEqual(fb["failing_stage"], "logic_coder")
                self.assertTrue(fb["suite_version"])
                self.assertTrue(fb["previously_passed_test_ids"])
                self.assertTrue(fb["failures"])
                plan = json.loads((root / "coder_plan.json").read_text(encoding="utf-8"))
                self.assertEqual(plan["profile"]["renderer"], renderer)
                for failure in fb["failures"]:
                    for k in ("test_id", "requirement_index", "expected", "actual", "error_category", "evidence_path", "attribution_evidence"):
                        self.assertIn(k, failure)
                    self.assertTrue(0 <= failure["requirement_index"] < len(plan["requirements"]))
                    evidence = (root / failure["evidence_path"]).resolve()
                    self.assertTrue(evidence.is_relative_to(root.resolve()))
                    self.assertTrue(evidence.is_file())


if __name__ == "__main__":
    unittest.main()
