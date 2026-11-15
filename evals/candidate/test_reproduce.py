"""Run the real CLI against authored scenes, not implementation-derived answers."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evals.candidate.test_fast_path import new_scene


class Reproduce(unittest.TestCase):
    def test_cli_saves_separate_contract_and_boundary_results(self):
        a = new_scene()
        b = new_scene("toggle", "after_commit")
        b["id"], b["observation"]["request_id"] = "toggle-new", "toggle-new-request"
        high = new_scene("send_message")
        high["id"], high["observation"]["request_id"] = "high-new", "high-new-request"
        high["observation"].update(risk="high", explicit_target=None)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "scenes.jsonl"
            source.write_text("".join(json.dumps(s) + "\n" for s in [a, b, high]))
            completed = subprocess.run([sys.executable, "-m", "evals.candidate.reproduce",
                "--scenarios", str(source), "--out", str(root / "runs")],
                capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            out = root / "runs"
            self.assertEqual((out / "before/traces.jsonl").read_text(),
                             (out / "after/traces.jsonl").read_text())
            report = json.loads((out / "comparison.json").read_text())
            zero = report["variants"]["fast_path"]["groups"]["simple_explicit_low"]
            twenty = report["variants"]["fast_path_20ms"]["groups"]["simple_explicit_low"]
            twenty_one = report["variants"]["fast_path_21ms"]["groups"]["simple_explicit_low"]
            self.assertEqual(zero["task_completed"]["numerator"], 2)
            self.assertEqual(zero["p95_latency_ms"], 580)
            self.assertEqual(twenty["p95_latency_ms"], 600)
            self.assertEqual(twenty_one["p95_latency_ms"], 601)
            self.assertEqual(report["variants"]["fast_path"]["changed_fallback_commits"], [])
            self.assertTrue((out / "rejected_small/oracle_summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
