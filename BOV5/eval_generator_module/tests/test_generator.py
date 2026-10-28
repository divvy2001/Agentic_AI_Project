import json
import tempfile
import unittest
from pathlib import Path
from eval_generator.generator import generate_suite


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "plans").mkdir()
        (self.root / "game").mkdir()
        (self.root / "game" / "main.py").write_text("print('WIN')\n", encoding="utf-8")
        plan = {
            "game_title": "Example",
            "profile": {"renderer": "terminal"},
            "requirements": [
                {"text": "Reach WIN after three actions", "check": "After three actions, WIN is observed"},
                {"text": "Do not win after two actions", "check": "After two actions, state is not WIN"}
            ]
        }
        manual = {
            "test_input": "1\\n1\\n1\\n",
            "expected_win_output": "WIN",
            "expected_lose_output": "LOSE",
            "notes": "fixture",
            "eval": {"tests": [{
                "test_id": "T01", "requirement_index": 0,
                "actions": [{"type": "stdin", "value": "1\\n"}],
                "observation": {"method": "stdout_contains", "value": "WIN"},
                "expected": "WIN appears"
            }]}
        }
        (self.root / "plans" / "coder_plan.json").write_text(json.dumps(plan), encoding="utf-8")
        (self.root / "plans" / "play_manual.json").write_text(json.dumps(manual), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_suite_and_marks_underspecified_requirement_not_testable(self):
        suite = generate_suite(self.root, "eval-v1")
        self.assertEqual(suite["summary"]["total"], 2)
        self.assertEqual(suite["tests"][0]["status"], "ready_for_validator")
        self.assertEqual(suite["tests"][1]["status"], "not_testable")
        output = self.root / "traces" / "eval" / "eval-v1" / "suite.json"
        self.assertTrue(output.is_file())
        self.assertNotIn("test_results.json", [p.name for p in output.parent.iterdir()])

    def test_refuses_changed_inputs_for_frozen_version(self):
        generate_suite(self.root, "eval-v1")
        p = self.root / "plans" / "coder_plan.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["game_title"] = "Changed"
        p.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(FileExistsError):
            generate_suite(self.root, "eval-v1")

    def test_rejects_path_traversal_version(self):
        with self.assertRaises(ValueError):
            generate_suite(self.root, "../bad")


if __name__ == "__main__":
    unittest.main()
