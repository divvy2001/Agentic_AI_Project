import unittest
from triage_agent.triage import deterministic_fallback, build_diagnostic_context

class TriageTests(unittest.TestCase):
    def test_asset_error_routes_asset(self):
        ctx = {"failures": [{"reason": "Failed to load texture player.png"}]}
        result = deterministic_fallback(ctx)
        self.assertEqual(result["route"], "asset")

    def test_harness_gap_routes_unknown(self):
        ctx = {"failures": [{"reason": "Unsupported action; requires pyautogui"}]}
        result = deterministic_fallback(ctx)
        self.assertEqual(result["route"], "unknown")

    def test_runtime_exception_routes_logic_with_low_confidence(self):
        ctx = {"failures": [{"reason": "Traceback: AssertionError"}]}
        result = deterministic_fallback(ctx)
        self.assertEqual(result["route"], "logic_coder")
        self.assertLess(result["confidence"], 0.65)

    def test_empty_failures_unknown(self):
        result = deterministic_fallback({"failures": []})
        self.assertEqual(result["route"], "unknown")

if __name__ == "__main__":
    unittest.main()
