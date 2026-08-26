#!/usr/bin/env python3
"""Generate deterministic relay workloads for verifier scenarios."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def build_workload(count: int, seed: int) -> dict:
    rng = random.Random(seed)
    rounds = []
    for i in range(count):
        rounds.append(
            {
                "round_index": i,
                "shard": rng.randrange(2),
                "op": "ping",
            }
        )
    return {
        "schema_version": 1,
        "workload_id": f"gen-{count}-{seed}",
        "rounds": rounds,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(build_workload(args.count, args.seed), indent=2) + "\n")


if __name__ == "__main__":
    main()
