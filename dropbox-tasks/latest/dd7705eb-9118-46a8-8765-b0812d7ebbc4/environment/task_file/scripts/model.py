import json
import math
from collections import defaultdict
from pathlib import Path


def _read_jobs(input_dir):
    return [json.loads(line) for line in (Path(input_dir) / "jobs.jsonl").read_text().splitlines() if line.strip()]


def _read_config(input_dir):
    return json.loads((Path(input_dir) / "config.json").read_text())


def _read_plan(output_dir):
    return json.loads((Path(output_dir) / "plan.json").read_text())


def _score_less_is_better(value, target, hard):
    if value <= target:
        return 1.0
    if value >= hard:
        return 0.0
    return max(0.0, 1.0 - (value - target) / (hard - target))


def _dependency_closure(required, deps):
    pred = defaultdict(list)
    for edge in deps:
        pred[edge["after"]].append(edge["before"])
    out = set(required)
    stack = list(required)
    while stack:
        cur = stack.pop()
        for p in pred.get(cur, []):
            if p not in out:
                out.add(p)
                stack.append(p)
    return out


def evaluate(input_dir="/app/task_file/input_data", output_dir="/app/task_file/output_data"):
    try:
        jobs = _read_jobs(input_dir)
        cfg = _read_config(input_dir)
        plan = _read_plan(output_dir)
    except Exception as exc:
        return {"error": f"failed to read inputs/output: {exc}"}

    if not isinstance(plan, dict) or not isinstance(plan.get("assignments"), list):
        return {"error": "plan.json must contain an assignments array"}

    job_by_id = {j["id"]: j for j in jobs}
    worker_by_id = {w["id"]: w for w in cfg["workers"]}
    if len(job_by_id) != len(jobs):
        return {"error": "duplicate input job ids"}

    assigned = {}
    for a in plan["assignments"]:
        if not isinstance(a, dict):
            return {"error": "assignment must be an object"}
        jid = a.get("job")
        wid = a.get("worker")
        st = a.get("start_time")
        if not isinstance(jid, str) or not isinstance(wid, str) or not isinstance(st, int) or isinstance(st, bool):
            return {"error": "assignment fields must be job string, worker string, integer start_time"}
        if jid not in job_by_id:
            return {"error": f"unknown job id {jid}"}
        if wid not in worker_by_id:
            return {"error": f"unknown worker id {wid}"}
        if jid in assigned:
            return {"error": f"duplicate assignment for {jid}"}
        if st < job_by_id[jid]["earliest_start"]:
            return {"error": f"{jid} starts before earliest_start"}
        assigned[jid] = {"worker": wid, "start": st, "finish": st + int(job_by_id[jid]["duration"])}

    mandatory = {j["id"] for j in jobs if j.get("mandatory")}
    required = _dependency_closure(mandatory, cfg.get("dependencies", []))
    if set(assigned) & mandatory != mandatory:
        return {"error": "not every mandatory job is scheduled"}
    missing_required = required - set(assigned)
    if missing_required:
        return {"error": f"required dependency jobs missing: {sorted(missing_required)[:4]}"}

    for edge in cfg.get("dependencies", []):
        before = edge["before"]
        after = edge["after"]
        if after in assigned:
            if before not in assigned:
                return {"error": f"scheduled {after} without dependency {before}"}
            if assigned[before]["finish"] > assigned[after]["start"]:
                return {"error": f"dependency violation {before}->{after}"}

    for a, b in cfg.get("conflicts", []):
        if a in assigned and b in assigned:
            return {"error": f"conflicting jobs both scheduled: {a}, {b}"}

    start = int(cfg["planning_start"])
    end = int(cfg["planning_end"])
    horizon = max(end, max((v["finish"] for v in assigned.values()), default=end))
    if any(v["start"] < start for v in assigned.values()):
        return {"error": "job starts before planning_start"}
    if horizon > end + 180:
        return {"error": "schedule extends too far beyond planning_end"}

    cpu_use = {w: defaultdict(int) for w in worker_by_id}
    net_use = defaultdict(int)
    finish_by_id = {jid: v["finish"] for jid, v in assigned.items()}
    validation_dependents = defaultdict(list)
    for edge in cfg.get("dependencies", []):
        if edge["before"] in assigned and edge["after"] in assigned and job_by_id[edge["after"]]["kind"] == "validate":
            validation_dependents[edge["before"]].append(edge["after"])

    scratch_events = []
    worker_minutes = defaultdict(int)
    for jid, t in assigned.items():
        job = job_by_id[jid]
        wid = t["worker"]
        worker_minutes[wid] += job["duration"]
        if job["cpu"] > worker_by_id[wid]["cpu"]:
            return {"error": f"{jid} exceeds worker cpu capacity"}
        release = t["finish"]
        for dep in validation_dependents.get(jid, []):
            release = max(release, finish_by_id[dep])
        scratch_events.append((t["start"], release, int(job["scratch_gb"])))
        for minute in range(t["start"], t["finish"]):
            cpu_use[wid][minute] += int(job["cpu"])
            net_use[minute] += int(job["network"])

    for wid, by_minute in cpu_use.items():
        cap = int(worker_by_id[wid]["cpu"])
        for minute, used in by_minute.items():
            if used > cap:
                return {"error": f"worker {wid} cpu exceeded at {minute}: {used}>{cap}"}
    max_network = max(net_use.values(), default=0)
    if max_network > int(cfg["network_capacity"]):
        return {"error": f"network capacity exceeded: {max_network}>{cfg['network_capacity']}"}

    scratch_by_minute = defaultdict(int)
    for st, fn, gb in scratch_events:
        for minute in range(st, fn):
            scratch_by_minute[minute] += gb
    max_scratch = max(scratch_by_minute.values(), default=0)
    if max_scratch > int(cfg["scratch_capacity_gb"]):
        return {"error": f"scratch capacity exceeded: {max_scratch}>{cfg['scratch_capacity_gb']}"}

    weighted_lateness = 0.0
    for jid, t in assigned.items():
        job = job_by_id[jid]
        weighted_lateness += max(0, t["finish"] - int(job["deadline"])) * int(job["priority"])

    datasets = cfg.get("datasets", [])
    fresh_score_sum = 0.0
    fresh_weight_sum = 0.0
    for d in datasets:
        ds = d["dataset"]
        target = int(d["target_time"])
        weight = float(d.get("weight", 1.0))
        finishes = [assigned[j["id"]]["finish"] for j in jobs if j["dataset"] == ds and j.get("produces_restore_point") and j["id"] in assigned]
        if finishes:
            best = min(finishes)
            val = _score_less_is_better(max(0, best - target), 0, 220)
        else:
            val = 0.0
        fresh_score_sum += val * weight
        fresh_weight_sum += weight
    freshness_score = fresh_score_sum / fresh_weight_sum if fresh_weight_sum else 1.0

    total_repl = sum(float(j.get("replication_value", 0)) for j in jobs)
    got_repl = sum(float(job_by_id[jid].get("replication_value", 0)) for jid, t in assigned.items() if job_by_id[jid]["kind"] == "replicate" and t["finish"] <= job_by_id[jid]["deadline"] + 60)
    replication_score = got_repl / total_repl if total_repl else 1.0

    avg_network = (sum(net_use.values()) / max(1, len(net_use))) if net_use else 0.0
    network_peak_ratio = max_network / max(1, int(cfg["network_capacity"]))
    network_score = max(0.0, 1.0 - max(0.0, network_peak_ratio - 1.0) / 0.10)
    if avg_network > 0:
        variance = sum((v - avg_network) ** 2 for v in net_use.values()) / len(net_use)
        network_score *= max(0.88, 1.0 - math.sqrt(variance) / max(1.0, cfg["network_capacity"] * 1.8))

    scratch_ratio = max_scratch / max(1, int(cfg["scratch_capacity_gb"]))
    scratch_score = max(0.0, 1.0 - max(0.0, scratch_ratio - 0.70) / 0.30)

    loads = [worker_minutes[w["id"]] for w in cfg["workers"]]
    if loads and max(loads) > 0:
        balance_spread = max(loads) - min(loads)
        balance_score = _score_less_is_better(balance_spread, 120, 430)
    else:
        balance_spread = 0
        balance_score = 0.0

    optional_gain = sum(float(job_by_id[jid].get("optional_value", 0)) for jid in assigned if not job_by_id[jid].get("mandatory"))
    possible_gain = sum(float(j.get("optional_value", 0)) for j in jobs if not j.get("mandatory"))
    optional_score = optional_gain / possible_gain if possible_gain else 1.0

    lateness_score = _score_less_is_better(weighted_lateness, 180, 1100)
    total_score = (
        0.27 * lateness_score
        + 0.20 * freshness_score
        + 0.15 * replication_score
        + 0.13 * network_score
        + 0.10 * scratch_score
        + 0.08 * balance_score
        + 0.07 * optional_score
    )

    return {
        "total_score": total_score,
        "lateness_score": lateness_score,
        "freshness_score": freshness_score,
        "replication_score": replication_score,
        "network_score": network_score,
        "scratch_score": scratch_score,
        "balance_score": balance_score,
        "optional_score": optional_score,
        "weighted_lateness": weighted_lateness,
        "max_network_peak": max_network,
        "max_scratch_gb": max_scratch,
        "balance_spread": balance_spread,
        "scheduled_jobs": len(assigned),
    }


if __name__ == "__main__":
    import sys
    inp = sys.argv[1] if len(sys.argv) > 1 else "/app/task_file/input_data"
    out = sys.argv[2] if len(sys.argv) > 2 else "/app/task_file/output_data"
    print(json.dumps(evaluate(inp, out), indent=2, sort_keys=True))
