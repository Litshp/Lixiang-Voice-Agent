"""Oracle-aware metrics for replayed Voice Agent traces."""
import json
from pathlib import Path
from voice_agent.evaluation import percentile


def _rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def align(scenes, runs):
    """Reject missing/duplicate/mismatched records rather than mis-score a zip."""
    scene_ids = [scene["id"] for scene in scenes]
    run_ids = [result["id"] for result in runs]
    if (len(set(scene_ids)) != len(scene_ids)
            or len(set(run_ids)) != len(run_ids)
            or set(scene_ids) != set(run_ids)):
        raise ValueError("scene and trace IDs must be unique and match exactly")
    by_id = {result["id"]: result for result in runs}
    pairs = [(scene, by_id[scene["id"]]) for scene in scenes]
    if any(scene["observation"] != result["observation"] for scene, result in pairs):
        raise ValueError("scene and trace observations must match")
    return pairs


def summarize_with_oracle(scenes, runs):
    if len(scenes) != len(runs) or not runs:
        raise ValueError("scenes and runs must be nonempty and aligned")
    pairs = align(scenes, runs)
    correct_once = 0
    task_completed = 0
    wrong_target = 0
    high_risk_wrong_target = 0
    high_risk_error = 0
    duplicate_non_idempotent = 0
    extra_commits = 0
    for scene, result in pairs:
        commits = result["commits"]
        target = scene["world"]["target"]
        action = scene["observation"]["action"]
        wrong = any(commit["target"] != target for commit in commits)
        duplicate = len(commits) > 1 and action in ("toggle", "send_message")
        correct_actions = all(commit["action"] == action for commit in commits)
        correct_once += len(commits) == 1 and not wrong and correct_actions
        task_completed += bool(commits) and not wrong and not duplicate and correct_actions
        wrong_target += wrong
        high_wrong = wrong and scene["observation"]["risk"] == "high"
        high_risk_wrong_target += high_wrong
        high_risk_error += high_wrong or duplicate
        duplicate_non_idempotent += duplicate
        extra_commits += max(0, len(commits) - 1)
    denominator = len(runs)
    return {
        "sessions": denominator,
        "correct_once": _rate(correct_once, denominator),
        "task_completed": _rate(task_completed, denominator),
        "wrong_target": _rate(wrong_target, denominator),
        "high_risk_wrong_target": _rate(high_risk_wrong_target,
            sum(s["observation"]["risk"] == "high" for s in scenes)),
        "high_risk_error": _rate(high_risk_error, denominator),
        "non_idempotent_duplicate": _rate(duplicate_non_idempotent, denominator),
        "extra_commits": extra_commits,
        "acknowledged": _rate(sum(result["acknowledged"] for result in runs), denominator),
        "clarified": _rate(sum(result["clarified"] for result in runs), denominator),
        "p95_latency_ms": percentile([result["latency_ms"] for result in runs], 0.95),
        "mean_model_cost_usd": round(
            sum(result["model_cost_usd"] for result in runs) / denominator, 6
        ),
    }


def summarize_groups(scenes, runs):
    pairs = align(scenes, runs)
    predicates = {
        "all": lambda o: True,
        "explicit_low": lambda o: o["risk"] == "low" and bool(o.get("explicit_target")),
        "simple_explicit_low": lambda o: o["risk"] == "low"
            and bool(o.get("explicit_target")) and not o.get("history"),
        "high_risk": lambda o: o["risk"] == "high",
        "ambiguous": lambda o: not o.get("explicit_target"),
    }
    groups = {}
    for name, predicate in predicates.items():
        selected = [(s, r) for s, r in pairs if predicate(s["observation"])]
        groups[name] = (summarize_with_oracle(
            [s for s, _ in selected], [r for _, r in selected]) if selected else None)
    return groups


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
