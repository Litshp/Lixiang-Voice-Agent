"""Hand-written outcomes, independent of the replay policy."""
from copy import deepcopy
import unittest

from evals.candidate.analyze import summarize_with_oracle, summarize_groups


def fixture(identifier, target, action="set_power", risk="low"):
    observation = {
        "request_id": identifier, "text": "测试指令", "action": action,
        "risk": risk, "explicit_target": target, "history": [],
    }
    scene = {"id": identifier, "observation": observation, "world": {"target": target}}
    result = {
        "id": identifier, "observation": deepcopy(observation),
        "commits": [{"target": target, "action": action, "key": identifier}],
        "latency_ms": 80, "model_cost_usd": 0,
        "acknowledged": True, "clarified": False,
    }
    return scene, result


class Metrics(unittest.TestCase):
    def test_reordered_traces_are_scored_by_id(self):
        a, ra = fixture("a", "atrium_blind")
        b, rb = fixture("b", "kitchen_purifier")
        summary = summarize_with_oracle([a, b], [rb, ra])
        self.assertEqual(summary["correct_once"]["numerator"], 2)

    def test_duplicate_missing_or_mismatched_trace_is_rejected(self):
        a, ra = fixture("a", "atrium_blind")
        b, rb = fixture("b", "kitchen_purifier")
        bad = deepcopy(ra)
        bad["observation"]["action"] = "toggle"
        for scenes, traces in [([a, b], [ra, ra]), ([a], [rb]), ([a, a], [ra, rb]), ([a], [bad])]:
            with self.subTest(traces=traces), self.assertRaises(ValueError):
                summarize_with_oracle(scenes, traces)

    def test_receipt_does_not_erase_wrong_target_or_duplicate(self):
        scene, result = fixture("msg", "recipient_new", "send_message", "high")
        wrong = deepcopy(result["commits"][0])
        wrong.update(target="recipient_other", key="wrong-first")
        result["commits"].insert(0, wrong)
        summary = summarize_with_oracle([scene], [result])
        self.assertEqual(summary["acknowledged"]["numerator"], 1)
        self.assertEqual(summary["task_completed"]["numerator"], 0)
        self.assertEqual(summary["wrong_target"]["numerator"], 1)
        self.assertEqual(summary["high_risk_wrong_target"]["denominator"], 1)
        self.assertEqual(summary["high_risk_error"]["numerator"], 1)
        self.assertEqual(summary["non_idempotent_duplicate"]["numerator"], 1)

    def test_repeated_set_power_keeps_outcome_but_repeated_toggle_does_not(self):
        for action, completed, duplicate in [("set_power", 1, 0), ("toggle", 0, 1), ("send_message", 0, 1)]:
            scene, result = fixture("repeat", "device_new", action)
            extra = dict(result["commits"][0], key="second")
            result["commits"].append(extra)
            summary = summarize_with_oracle([scene], [result])
            with self.subTest(action=action):
                self.assertEqual(summary["correct_once"]["numerator"], 0)
                self.assertEqual(summary["task_completed"]["numerator"], completed)
                self.assertEqual(summary["non_idempotent_duplicate"]["numerator"], duplicate)
                self.assertEqual(summary["extra_commits"], 1)

    def test_simple_group_excludes_high_risk_and_contextual_commands(self):
        a, ra = fixture("simple", "atrium_blind")
        b, rb = fixture("context", "atrium_blind")
        b["observation"]["history"] = ["用户：之前选过这个。"]
        rb["observation"] = deepcopy(b["observation"])
        c, rc = fixture("high", "recipient_new", "send_message", "high")
        groups = summarize_groups([a, b, c], [rc, rb, ra])
        self.assertEqual(groups["simple_explicit_low"]["sessions"], 1)
        self.assertEqual(groups["explicit_low"]["sessions"], 2)
        self.assertEqual(groups["high_risk"]["sessions"], 1)


if __name__ == "__main__":
    unittest.main()
