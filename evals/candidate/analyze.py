"""Oracle-aware metrics for replayed Voice Agent traces."""
import json
from math import ceil
from pathlib import Path


def _rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else 0.0,
    }


def _p95(values):
    return sorted(values)[max(0, ceil(0.95 * len(values)) - 1)] if values else None


def summarize_with_oracle(scenes, runs):
    if len(scenes) != len(runs) or not runs:
        raise ValueError("scenes and runs must be nonempty and aligned")
    correct_once = 0
    wrong_target = 0
    duplicate_non_idempotent = 0
    for scene, result in zip(scenes, runs):
        commits = result["commits"]
        target = scene["world"]["target"]
        action = scene["observation"]["action"]
        correct_once += len(commits) == 1 and commits[0]["target"] == target
        wrong_target += any(commit["target"] != target for commit in commits)
        duplicate_non_idempotent += (
            len(commits) > 1 and action in ("toggle", "send_message")
        )
    denominator = len(runs)
    return {
        "sessions": denominator,
        "correct_once": _rate(correct_once, denominator),
        "wrong_target": _rate(wrong_target, denominator),
        "non_idempotent_duplicate": _rate(duplicate_non_idempotent, denominator),
        "acknowledged": _rate(sum(result["acknowledged"] for result in runs), denominator),
        "clarified": _rate(sum(result["clarified"] for result in runs), denominator),
        "p95_latency_ms": _p95([result["latency_ms"] for result in runs]),
        "mean_model_cost_usd": round(
            sum(result["model_cost_usd"] for result in runs) / denominator, 6
        ),
    }


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", default="data/public_scenarios.jsonl")
    parser.add_argument("--traces", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    summary = summarize_with_oracle(
        load_jsonl(args.scenarios), load_jsonl(args.traces)
    )
    output = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(output)
    print(output, end="")
