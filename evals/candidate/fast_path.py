"""Independent fast-path experiment for confirmed low-risk commands."""
from copy import deepcopy

from voice_agent import policy as baseline
from voice_agent.simulator import validate, run as run_baseline


ALLOWED_ACTIONS = {"set_power", "toggle", "send_message"}


def is_fast_path_eligible(observation):
    """Use only the product-provided confirmed target and risk fields."""
    return (
        observation.get("risk") == "low"
        and bool(observation.get("explicit_target"))
        and observation.get("action") in ALLOWED_ACTIONS
    )


def _run_direct(scene):
    validate(scene)
    obs, world = deepcopy(scene["observation"]), scene["world"]
    target = obs["explicit_target"]
    events = [{"type": "rule", "kind": "execute", "target": target}]
    latency, acknowledged = 0, False
    commits, seen_keys = [], set()
    first_key = obs["request_id"] + ":action"

    def commit(key):
        if key in seen_keys:
            events.append({"type": "deduplicated", "key": key})
            return
        seen_keys.add(key)
        effect = {"target": target, "action": obs["action"], "key": key}
        commits.append(effect)
        events.append({"type": "tool_committed", **effect})

    mode = world["timeout"]
    latency += 80 if mode == "none" else 500
    if mode != "before_commit":
        commit(first_key)
    if mode == "none":
        acknowledged = True
    else:
        events.append({"type": "tool_timeout", "key": first_key})
        retry = baseline.retry_key(deepcopy(obs), {
            "original_key": first_key, "target": target, "attempt": 1,
        })
        if retry is not None:
            latency += 80
            commit(retry)
            acknowledged = True
    events.append({"type": "assistant_response", "accepted": acknowledged})
    if any(c["target"] != world["target"] for c in commits):
        events.append({"type": "user_signal", "signal": "user_correction"})
    if len(commits) > 1 and obs["action"] in ("toggle", "send_message"):
        events.append({"type": "user_signal", "signal": "user_complaint"})
    for signal in world.get("signals", []):
        events.append({"type": "user_signal", "signal": signal})
    return {
        "id": scene["id"], "observation": obs, "events": events,
        "latency_ms": latency, "model_cost_usd": 0,
        "clarified": False, "acknowledged": acknowledged,
        "commits": commits,
    }


def run(scene):
    """Run the fast path and delegate all other scenes to the unchanged baseline."""
    if is_fast_path_eligible(scene["observation"]):
        return _run_direct(scene)
    return run_baseline(scene, baseline)
