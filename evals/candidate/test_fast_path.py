from copy import deepcopy
import unittest

from evals.candidate.fast_path import decide, is_fast_path_eligible, run
from evals.candidate.analyze import summarize_with_oracle
from voice_agent import policy
from voice_agent.simulator import run as run_baseline
from voice_agent.evaluation import load_scenes


def new_scene(action="set_power", timeout="none"):
    """Author-defined intent: explicitly operate on a new device/recipient."""
    return {
        "id": "new-command",
        "observation": {
            "request_id": "new-request", "text": "操作 courtyard_purifier",
            "action": action, "risk": "low", "explicit_target": "courtyard_purifier",
            "history": [], "interaction_mode": "busy",
        },
        "models": {m: {"candidates": [{"target": "wrong_device", "confidence": 0.999}]}
                   for m in ("small", "standard", "strong")},
        "world": {"target": "courtyard_purifier", "timeout": timeout,
                  "clarification_answered": False, "signals": []},
    }


class FastPath(unittest.TestCase):
    def test_rule_overhead_is_charged_even_on_fallback(self):
        for risk in ("low", "high"):
            scene = new_scene()
            scene["observation"]["risk"] = risk
            zero = run(scene)
            charged = run(scene, rule_latency_ms=21)
            with self.subTest(risk=risk):
                self.assertEqual(charged["latency_ms"], zero["latency_ms"] + 21)
                self.assertEqual(charged["commits"], zero["commits"])
                self.assertEqual(charged["model_cost_usd"], zero["model_cost_usd"])

    def test_negative_or_nonfinite_rule_overhead_is_rejected(self):
        for overhead in (-1, float("nan"), float("inf")):
            with self.subTest(overhead=overhead), self.assertRaises(ValueError):
                run(new_scene(), rule_latency_ms=overhead)

    def test_decision_has_no_world_access_and_does_not_repair_bad_confirmation(self):
        scene = new_scene()
        observed = deepcopy(scene["observation"])
        self.assertEqual(decide(observed), {"kind": "execute", "target": "courtyard_purifier"})
        before = run(scene)
        scene["world"]["target"] = "another_intended_device"
        after = run(scene)
        self.assertEqual(before["commits"], after["commits"])
        self.assertEqual(observed, scene["observation"])
        summary = summarize_with_oracle([scene], [after])
        self.assertEqual(summary["wrong_target"]["numerator"], 1)

    def test_new_targets_with_missing_model_candidate_execute_once_for_all_actions(self):
        for action in ("set_power", "toggle", "send_message"):
            for timeout, latency in [("none", 80), ("before_commit", 580), ("after_commit", 580)]:
                scene = new_scene(action, timeout)
                untouched = deepcopy(scene)
                result = run(scene)
                with self.subTest(action=action, timeout=timeout):
                    self.assertEqual(scene, untouched)
                    self.assertEqual(result["commits"], [{"target": "courtyard_purifier",
                        "action": action, "key": "new-request:action"}])
                    self.assertEqual(result["latency_ms"], latency)
                    self.assertFalse(result["clarified"])

    def test_high_risk_and_ambiguous_inputs_replay_identically(self):
        for risk, explicit in [("high", "courtyard_purifier"), ("high", None), ("low", None)]:
            scene = new_scene("send_message")
            scene["observation"].update(risk=risk, explicit_target=explicit)
            with self.subTest(risk=risk, explicit=explicit):
                self.assertEqual(run(scene), run_baseline(scene, policy))

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
