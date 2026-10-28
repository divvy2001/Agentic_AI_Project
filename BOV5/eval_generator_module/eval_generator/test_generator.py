import unittest
from eval_generator.generator import _validate_and_normalize_tests

class GeneratorTests(unittest.TestCase):
    def test_invalid_test_becomes_not_testable_and_requirement_covered_by_placeholder(self):
        warnings = []
        requirements = [{"text": "Player can move"}, {"text": "Player can win"}]
        tests = _validate_and_normalize_tests([
            {"test_id": "T01", "requirement_index": 0, "status": "ready_for_validator",
             "actions": [], "observation": {"method": "game_state"}, "expected": "moves"}
        ], requirements, "pygame", warnings)
        self.assertEqual(len(tests), 2)
        self.assertEqual(tests[0]["status"], "not_testable")
        self.assertEqual(tests[1]["status"], "not_testable")

    def test_valid_test_is_ready(self):
        warnings = []
        requirements = [{"text": "Player can move"}]
        tests = _validate_and_normalize_tests([
            {"test_id": "T01", "requirement_index": 0, "status": "ready_for_validator",
             "actions": [{"type": "press", "value": "left"}],
             "observation": {"method": "game_state", "target": "player_x"},
             "expected": "player_x decreases"}
        ], requirements, "pygame", warnings)
        self.assertEqual(tests[0]["status"], "ready_for_validator")

if __name__ == "__main__":
    unittest.main()
