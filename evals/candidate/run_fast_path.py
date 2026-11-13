"""Replay public scenarios with the independent fast-path experiment."""
import argparse
import json
from pathlib import Path

from voice_agent.evaluation import load_scenes, summarize

from evals.candidate.fast_path import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", default="data/public_scenarios.jsonl")
    parser.add_argument("--out", default="runs/fast_path")
    args = parser.parse_args()
    scenes = load_scenes(args.scenarios)
    results = [run(scene) for scene in scenes]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "traces.jsonl").write_text(
        "".join(json.dumps(result, ensure_ascii=False) + "\n" for result in results)
    )
    summary = summarize(results)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "ok", "summary": summary, "output": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
