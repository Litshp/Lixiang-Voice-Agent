"""Reproduce original-contract, rejected-route and boundary results separately."""
import argparse
from functools import partial
import json
from pathlib import Path

from voice_agent import policy
from voice_agent.evaluation import load_scenes, summarize
from voice_agent.simulator import run as baseline_run
from evals.candidate.analyze import summarize_groups, summarize_with_oracle
from evals.candidate.fast_path import is_fast_path_eligible, run as fast_run


class SmallExplicitLow:
    """Rejected comparator: cheap routing can omit a confirmed target."""
    @staticmethod
    def select_model(request):
        if request["risk"] == "low" and request.get("explicit_target"):
            return "small"
        return policy.select_model(request)

    choose_action = staticmethod(policy.choose_action)
    retry_key = staticmethod(policy.retry_key)


def save_run(folder, scenes, results):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "traces.jsonl").write_text("".join(
        json.dumps(result, ensure_ascii=False) + "\n" for result in results))
    metrics = summarize_with_oracle(scenes, results)
    groups = summarize_groups(scenes, results)
    for name, value in [("summary", summarize(results)),
                        ("oracle_summary", metrics), ("groups", groups)]:
        (folder / (name + ".json")).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return {"metrics": metrics, "groups": groups}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", default="data/public_scenarios.jsonl")
    parser.add_argument("--out", default="runs")
    args = parser.parse_args()
    scenes = load_scenes(args.scenarios)
    original = [baseline_run(scene, policy) for scene in scenes]
    out = Path(args.out)
    report = {
        "source": args.scenarios,
        "original_contract_final": "after (baseline retained)",
        "boundary_only": ["fast_path", "fast_path_20ms", "fast_path_21ms"],
        "assumptions": {
            "explicit_target": "Trusted confirmed target; not inferred from world",
            "rule_latency_ms": "0/20/21 are assumed sensitivity values, not measurements",
            "model_cost": "Model calls only; upstream confirmation/infrastructure costs unknown",
        },
        "variants": {},
    }
    runners = {
        "before": None,
        "after": None,
        "rejected_small": partial(baseline_run, policy=SmallExplicitLow),
        "fast_path": fast_run,
        "fast_path_20ms": partial(fast_run, rule_latency_ms=20),
        "fast_path_21ms": partial(fast_run, rule_latency_ms=21),
    }
    for name, runner in runners.items():
        results = [runner(scene) for scene in scenes] if runner else original
        variant = save_run(out / name, scenes, results)
        variant["changed_fallback_commits"] = [
            scene["id"] for scene, before, after in zip(scenes, original, results)
            if not is_fast_path_eligible(scene["observation"])
            and before["commits"] != after["commits"]
        ]
        report["variants"][name] = variant
    (out / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"comparison": str(out / "comparison.json"),
                      "original_contract_final": "baseline retained"}))


if __name__ == "__main__":
    main()
