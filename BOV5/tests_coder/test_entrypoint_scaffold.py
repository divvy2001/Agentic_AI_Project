"""Offline safety tests for public workflow entrypoints (no OpenRouter calls)."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coder_agent_adhoc import repair, initial_build


class EntrypointContractTests(unittest.TestCase):
    def test_build_entrypoint_readonly_dry_run(self):
        result = initial_build.run_initial_build(dry_run=True)
        self.assertEqual(result["status"], "dry_run")
        self.assertIn(result["renderer"], {"pygame", "godot", "terminal"})

    def test_all_wrong_stages_block_without_llm(self):
        fixture = Path(__file__).parent / "fixtures" / "terminal"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plans").mkdir()
            (root / "game").mkdir()
            (root / "game/main.py").write_text("print('hello')\n")
            (root / "plans/coder_plan.json").write_bytes((fixture / "coder_plan.json").read_bytes())
            (root / "traces/eval/eval-v1").mkdir(parents=True)
            (root / "traces/eval/eval-v1/T03.log").write_text("test log")
            fb = json.loads((fixture / "feedback.json").read_text())
            game_hash = hashlib.sha256((root / "game/main.py").read_bytes()).hexdigest()
            with patch.object(repair, "ROOT", root), patch.object(repair, "PLAN_FILE", root / "plans/coder_plan.json"), patch.object(repair, "GAME_DIR", root / "game"):
                p = root / "traces/eval/eval-v1/test_results.json"
                for stage in ("asset", "planner", "runtime_eval_generator", "unknown"):
                    fb["failing_stage"] = stage
                    p.write_text(json.dumps(fb))
                    result = repair.run_repair("traces/eval/eval-v1/test_results.json")
                    self.assertEqual(result["status"], "blocked")
                    self.assertEqual(result["reason"], "wrong_failing_stage")
                    self.assertEqual(hashlib.sha256((root / "game/main.py").read_bytes()).hexdigest(), game_hash)
                fb["status"] = "inconclusive"
                fb["failing_stage"] = "unknown"
                fb["failures"] = []
                p.write_text(json.dumps(fb))
                self.assertEqual(repair.run_repair("traces/eval/eval-v1/test_results.json")["status"], "blocked")

    def test_valid_feedback_dispatches_shared_core_without_mutation(self):
        fixture = Path(__file__).parent / "fixtures" / "terminal"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plans").mkdir()
            (root / "game").mkdir()
            (root / "game/main.py").write_text("print('hello')\n")
            (root / "plans/coder_plan.json").write_bytes((fixture / "coder_plan.json").read_bytes())
            fb = json.loads((fixture / "feedback.json").read_text())
            f = root / "traces/eval/eval-v1/test_results.json"
            f.parent.mkdir(parents=True)
            f.write_text(json.dumps(fb))
            (f.parent / "T03.log").write_text("test log")
            with patch.object(repair, "ROOT", root), patch.object(repair, "PLAN_FILE", root / "plans/coder_plan.json"), patch.object(repair, "GAME_DIR", root / "game"):
                with patch("coder_agent_adhoc.agent_coder.run_coder", return_value={"status":"dry_run"}):
                    dry = repair.run_repair("traces/eval/eval-v1/test_results.json", dry_run=True)
                    self.assertEqual(dry["status"], "dry_run")
                with patch("coder_agent_adhoc.agent_coder.run_coder", return_value={"status":"ready_for_testing"}) as core:
                    real = repair.run_repair("traces/eval/eval-v1/test_results.json")
                    self.assertEqual(real["status"], "ready_for_testing")
                    core.assert_called_once_with(dry_run=False, mode="repair", feedback_path="traces/eval/eval-v1/test_results.json")


    def test_path_traversal_rejected(self):
        self.assertEqual(repair.run_repair("../outside.json")["status"], "blocked")
        self.assertIn("invalid_feedback", repair.run_repair("../outside.json")["reason"])


if __name__ == "__main__":
    unittest.main()
