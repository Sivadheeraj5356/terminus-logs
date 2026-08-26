#!/usr/bin/env python3
"""Materialize deterministic protein-design instances and reference objectives."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


SCALARS = (
    "n_residues",
    "n_rotamers",
    "n_states",
    "n_classes",
    "n_bridges",
    "required_bridges",
    "mutation_budget",
    "charge_min",
    "charge_max",
    "target_state",
    "robust_weight",
    "mutation_weight",
    "exposure_weight",
)
ARRAYS = (
    ("valid", ("n_residues", "n_rotamers")),
    ("native_rotamer", ("n_residues",)),
    ("aa_class", ("n_residues", "n_rotamers")),
    ("charge", ("n_residues", "n_rotamers")),
    ("exposure_penalty", ("n_residues", "n_rotamers")),
    ("mutation_penalty", ("n_residues", "n_rotamers")),
    ("unary_energy", ("n_states", "n_residues", "n_rotamers")),
    ("contact", ("n_residues", "n_residues")),
    (
        "pair_energy",
        ("n_states", "n_residues", "n_rotamers", "n_residues", "n_rotamers"),
    ),
    ("clash", ("n_residues", "n_rotamers", "n_residues", "n_rotamers")),
    ("bridge_left", ("n_bridges",)),
    ("bridge_right", ("n_bridges",)),
    ("bridge_capable", ("n_residues", "n_rotamers")),
    ("bridge_credit", ("n_states", "n_bridges")),
    ("class_min", ("n_classes",)),
    ("class_max", ("n_classes",)),
    ("stability_margin", ("n_states",)),
)


def tensor(shape, fn, prefix=()):
    if len(shape) == 1:
        return [fn(prefix + (i,)) for i in range(shape[0])]
    return [tensor(shape[1:], fn, prefix + (i,)) for i in range(shape[0])]


def flatten(value):
    if not isinstance(value, list):
        return [value]
    result = []
    for item in value:
        result.extend(flatten(item))
    return result


def dzn_text(instance):
    lines = [f"{name} = {instance[name]};" for name in SCALARS]
    for name, dimensions in ARRAYS:
        sizes = [instance[key] for key in dimensions]
        indices = ", ".join(f"1..{size}" for size in sizes)
        values = ", ".join(str(value) for value in flatten(instance[name]))
        lines.append(f"{name} = array{len(sizes)}d({indices}, [{values}]);")
    return "\n".join(lines) + "\n"


def base_case(seed, rich=False):
    residues = 7 if rich else 4 + seed % 3
    rotamers = 3 if rich or seed % 4 else 2
    states = 4 if rich or seed % 2 else 3
    classes = 3 if residues >= 5 else 2
    edges = [(r, r + 1) for r in range(residues - 1)]
    if residues >= 5:
        edges.append((0, residues - 1))
    bridges = len(edges)
    capable = min(1, rotamers - 1)
    instance = {
        "n_residues": residues,
        "n_rotamers": rotamers,
        "n_states": states,
        "n_classes": classes,
        "n_bridges": bridges,
        "required_bridges": 1 + int(rich),
        "mutation_budget": residues,
        "charge_min": -residues,
        "charge_max": residues,
        "target_state": 1,
        "robust_weight": 10_000,
        "mutation_weight": 2 + seed % 3,
        "exposure_weight": 2 + (seed + 1) % 3,
    }
    instance["valid"] = tensor(
        (residues, rotamers),
        lambda x: int(not (rotamers == 3 and x[1] == 2 and (x[0] + seed) % 5 == 0)),
    )
    instance["native_rotamer"] = [1] * residues
    instance["aa_class"] = tensor(
        (residues, rotamers), lambda x: 1 + (x[0] + 2 * x[1] + seed) % classes
    )
    instance["charge"] = tensor(
        (residues, rotamers), lambda x: ((x[0] + x[1] + seed) % 3) - 1
    )
    instance["exposure_penalty"] = tensor(
        (residues, rotamers), lambda x: 1 + (2 * x[0] + x[1] + seed) % 7
    )
    instance["mutation_penalty"] = tensor(
        (residues, rotamers), lambda x: 0 if x[1] == 0 else 2 + (x[0] + x[1] + seed) % 6
    )
    instance["unary_energy"] = tensor(
        (states, residues, rotamers),
        lambda x: 8 + 5 * x[0] + (3 * x[1] + 2 * x[2] + seed) % 9,
    )
    instance["contact"] = tensor(
        (residues, residues),
        lambda x: int(
            x[0] != x[1]
            and (
                abs(x[0] - x[1]) == 1
                or (x[0] + x[1] + seed) % 4 == 0
            )
        ),
    )
    instance["pair_energy"] = tensor(
        (states, residues, rotamers, residues, rotamers),
        lambda x: 1 + (2 * x[0] + x[1] + 3 * x[2] + x[3] + 2 * x[4] + seed) % 8,
    )
    instance["clash"] = tensor(
        (residues, rotamers, residues, rotamers),
        lambda x: int(
            x[0] < x[2]
            and (x[0] + 2 * x[1] + 3 * x[2] + x[3] + seed) % 29 == 0
        ),
    )
    instance["bridge_left"] = [left + 1 for left, _ in edges]
    instance["bridge_right"] = [right + 1 for _, right in edges]
    instance["bridge_capable"] = tensor(
        (residues, rotamers), lambda x: int(x[1] == capable)
    )
    instance["bridge_credit"] = tensor(
        (states, bridges), lambda x: 1 + (x[0] + 2 * x[1] + seed) % 4
    )
    instance["class_min"] = [0] * classes
    instance["class_max"] = [residues] * classes
    instance["stability_margin"] = [0] + [2 + s % 2 for s in range(1, states)]
    return instance


def clash_case():
    instance = base_case(100)
    residues = instance["n_residues"]
    rotamers = instance["n_rotamers"]
    states = instance["n_states"]
    instance["unary_energy"] = tensor(
        (states, residues, rotamers),
        lambda x: 5 + 5 * x[0] + (0 if x[2] == 0 else 12),
    )
    instance["contact"] = tensor(
        (residues, residues), lambda x: int({x[0], x[1]} == {0, 1})
    )
    instance["pair_energy"] = tensor(
        (states, residues, rotamers, residues, rotamers), lambda _: 0
    )
    instance["clash"] = tensor(
        (residues, rotamers, residues, rotamers),
        lambda x: int(x[0] == 0 and x[1] == 0 and x[2] == 1 and x[3] == 0),
    )
    return instance


def stability_case():
    instance = base_case(101)
    residues = instance["n_residues"]
    rotamers = instance["n_rotamers"]
    states = instance["n_states"]

    def unary(index):
        state, residue, rotamer = index
        if residue == 0:
            if rotamer == 0:
                return [4, 0, 4, 4][state]
            return [5, 7, 7, 7][state]
        return 8 + rotamer

    instance["unary_energy"] = tensor((states, residues, rotamers), unary)
    instance["pair_energy"] = tensor(
        (states, residues, rotamers, residues, rotamers), lambda _: 0
    )
    instance["clash"] = tensor(
        (residues, rotamers, residues, rotamers), lambda _: 0
    )
    instance["bridge_credit"] = tensor(
        (states, instance["n_bridges"]), lambda x: 1 + x[1] % 2
    )
    instance["stability_margin"] = [0] + [2] * (states - 1)
    return instance


def bridge_matching_case():
    residues, rotamers, states, classes = 4, 2, 3, 2
    edges = [(0, 1), (1, 2), (2, 3)]
    instance = {
        "n_residues": residues,
        "n_rotamers": rotamers,
        "n_states": states,
        "n_classes": classes,
        "n_bridges": len(edges),
        "required_bridges": 2,
        "mutation_budget": residues,
        "charge_min": -residues,
        "charge_max": residues,
        "target_state": 1,
        "robust_weight": 10_000,
        "mutation_weight": 1,
        "exposure_weight": 1,
        "valid": tensor((residues, rotamers), lambda _: 1),
        "native_rotamer": [1] * residues,
        "aa_class": tensor((residues, rotamers), lambda x: 1 + (x[0] + x[1]) % classes),
        "charge": tensor((residues, rotamers), lambda _: 0),
        "exposure_penalty": tensor((residues, rotamers), lambda _: 1),
        "mutation_penalty": tensor((residues, rotamers), lambda x: x[1]),
        "unary_energy": tensor(
            (states, residues, rotamers), lambda x: 12 + 4 * x[0] + x[2]
        ),
        "contact": tensor((residues, residues), lambda _: 0),
        "pair_energy": tensor(
            (states, residues, rotamers, residues, rotamers), lambda _: 0
        ),
        "clash": tensor(
            (residues, rotamers, residues, rotamers), lambda _: 0
        ),
        "bridge_left": [edge[0] + 1 for edge in edges],
        "bridge_right": [edge[1] + 1 for edge in edges],
        "bridge_capable": tensor((residues, rotamers), lambda _: 1),
        "bridge_credit": [[10, 9, 1], [10, 9, 1], [10, 9, 1]],
        "class_min": [0, 0],
        "class_max": [residues, residues],
        "stability_margin": [0, 2, 2],
    }
    return instance


def build_case(seed, rich=False):
    if not rich and seed == 0:
        return clash_case()
    if not rich and seed == 1:
        return stability_case()
    if not rich and seed == 2:
        return bridge_matching_case()
    return base_case(seed, rich)


def last_json(stdout):
    blocks = [part for part in stdout.split("----------") if "{" in part]
    if not blocks:
        raise ValueError("no JSON solution")
    block = blocks[-1]
    return json.loads(block[block.index("{") : block.rindex("}") + 1])


def solve(model, instance):
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "case.dzn"
        data.write_text(dzn_text(instance), encoding="utf-8")
        result = subprocess.run(
            [
                "minizinc",
                "--solver",
                "highs",
                "--output-mode",
                "json",
                "--output-objective",
                str(model),
                str(data),
            ],
            cwd="/app",
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    if result.returncode != 0 or "==========" not in result.stdout:
        raise RuntimeError((result.stdout + result.stderr)[-4000:])
    return last_json(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--solve", action="store_true")
    args = parser.parse_args()
    root = args.task_root
    visible = build_case(997, rich=True)
    (root / "environment" / "instance.json").write_text(
        json.dumps(visible, indent=2) + "\n", encoding="utf-8"
    )
    (root / "environment" / "instance.dzn").write_text(
        dzn_text(visible), encoding="utf-8"
    )
    cases = [
        {"id": f"case-{seed:02d}", "instance": build_case(seed)}
        for seed in range(60)
    ]
    if args.solve:
        model = root / "solution" / "model_correct.mzn"
        for item in cases:
            item["objective"] = solve(model, item["instance"])["total_cost"]
        visible_solution = solve(model, visible)
        receipt = {
            "visible_objective": visible_solution["total_cost"],
            "cases": cases,
        }
    else:
        receipt = {"visible_objective": None, "cases": cases}
    (root / "tests" / "fixtures" / "cases.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
