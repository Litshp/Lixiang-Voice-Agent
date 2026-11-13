import json
import unittest

from evals.candidate.fast_path import is_fast_path_eligible, run
from evals.candidate.analyze import summarize_with_oracle
from voice_agent.evaluation import load_scenes


class FastPath(unittest.TestCase):
    def test_confirmed_low_risk_target_bypasses_model(self):
        scene = load_scenes("data/public_scenarios.jsonl")[0]
        result = run(scene)

        self.assertTrue(is_fast_path_eligible(scene["observation"]))
        self.assertEqual(result["model_cost_usd"], 0)
        self.assertEqual(result["latency_ms"], 80)
        self.assertEqual(result["commits"][0]["target"], scene["world"]["target"])
        self.assertEqual(result["events"][0]["type"], "rule")

    def test_ambiguous_request_stays_on_baseline(self):
        scene = next(
            s for s in load_scenes("data/public_scenarios.jsonl")
            if not s["observation"]["explicit_target"]
        )
        result = run(scene)

        self.assertFalse(is_fast_path_eligible(scene["observation"]))
        self.assertEqual(result["events"][0]["type"], "model")
        self.assertGreater(result["model_cost_usd"], 0)

    def test_high_risk_explicit_target_does_not_bypass_model(self):
        scene = next(
            s for s in load_scenes("data/public_scenarios.jsonl")
            if s["observation"]["risk"] == "high"
            and s["observation"]["explicit_target"]
        )
        result = run(scene)

        self.assertFalse(is_fast_path_eligible(scene["observation"]))
        self.assertEqual(result["events"][0]["type"], "model")
        self.assertGreater(result["model_cost_usd"], 0)

    def test_fast_path_keeps_same_key_retry_idempotent(self):
        scene = load_scenes("data/public_scenarios.jsonl")[0]
        scene["world"]["timeout"] = "after_commit"
        result = run(scene)

        self.assertEqual(len(result["commits"]), 1)
        self.assertEqual(result["latency_ms"], 580)

    def test_oracle_metrics_distinguish_ack_from_correct_completion(self):
        scene = load_scenes("data/public_scenarios.jsonl")[0]
        result = run(scene)
        summary = summarize_with_oracle([scene], [result])

        self.assertEqual(summary["correct_once"], {"numerator": 1, "denominator": 1, "rate": 1.0})
        self.assertEqual(summary["wrong_target"], {"numerator": 0, "denominator": 1, "rate": 0.0})


if __name__ == "__main__":
    unittest.main()
