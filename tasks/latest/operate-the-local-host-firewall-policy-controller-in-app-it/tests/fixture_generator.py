"""Generate bounded deterministic policy cases."""

from __future__ import annotations

import json
import random
from pathlib import Path


def write_case(root: Path, seed: int) -> dict:
    rng = random.Random(seed)
    tenant = f"t{seed}"
    rules = {}
    sets = {}
    n_rules = 2 + seed % 3
    for i in range(n_rules):
        rid = f"rule-{i}"
        rules[rid] = {
            "action": rng.choice(["allow", "drop"]),
            "ordered_index": i,
            "dst_port": 80 + i,
        }
    sets["web-clients"] = {"members": [f"10.{seed}.{i}.1" for i in range(3)]}
    base = f'''priority = 0\ntenant = "{tenant}"\n\n[sets.web-clients]\nmembers = {json.dumps(sets["web-clients"]["members"])}\n\n'''
    for rid, rule in rules.items():
        base += f"[rules.{rid}]\naction = \"{rule['action']}\"\nordered_index = {rule['ordered_index']}\ndst_port = {rule['dst_port']}\n\n"
    cfg_dir = root / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "base.toml").write_text(base)
    (cfg_dir / "conf.d").mkdir(exist_ok=True)
    return {"tenant": tenant, "rules": rules, "seed": seed}
