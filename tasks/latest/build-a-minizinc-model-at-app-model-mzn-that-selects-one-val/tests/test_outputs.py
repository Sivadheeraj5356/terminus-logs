"""Behavioral verification for multistate protein rotamer design."""

from __future__ import annotations

import json
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import pytest

from gen_cases import dzn_text


APP = Path("/app")
MODEL = APP / "model.mzn"
RECEIPT = json.loads((Path(__file__).parent / "fixtures" / "cases.json").read_text())


def _last_json(text):
    blocks = [part for part in text.split("----------") if "{" in part]
    if not blocks:
        raise ValueError("no JSON solution")
    block = blocks[-1]
    return json.loads(block[block.index("{") : block.rindex("}") + 1])


@lru_cache(maxsize=None)
def _solve(case_id):
    if case_id == "visible":
        data = APP / "instance.dzn"
    else:
        item = next(item for item in RECEIPT["cases"] if item["id"] == case_id)
        data = Path(tempfile.gettempdir()) / f"protein-rotamer-{case_id}.dzn"
        data.write_text(dzn_text(item["instance"]), encoding="utf-8")
    result = subprocess.run(
        [
            "minizinc",
            "--solver",
            "highs",
            "--output-mode",
            "json",
            "--output-objective",
            str(MODEL),
            str(data),
        ],
        cwd=APP,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0 or "==========" not in result.stdout:
        return {"_execution_error": (result.stdout + result.stderr)[-4000:]}
    try:
        return _last_json(result.stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        return {"_execution_error": str(exc)}


def _shape(value, dimensions, binary=False):
    if not dimensions:
        return type(value) is int
    if not isinstance(value, list) or len(value) != dimensions[0]:
        return False
    if len(dimensions) == 1:
        if binary:
            return all(type(item) is int and item in (0, 1) for item in value)
        return all(type(item) is int for item in value)
    return all(_shape(item, dimensions[1:], binary) for item in value)


def _validate(instance, solution, expected):
    if "_execution_error" in solution:
        return [solution["_execution_error"]]
    residues = instance["n_residues"]
    rotamers = instance["n_rotamers"]
    states = instance["n_states"]
    classes = instance["n_classes"]
    bridges = instance["n_bridges"]
    shapes = {
        "select": ((residues, rotamers), True),
        "bridge": ((bridges,), True),
        "class_count": ((classes,), False),
        "state_energy": ((states,), False),
    }
    errors = []
    for name, (dimensions, binary) in shapes.items():
        if name not in solution or not _shape(solution[name], dimensions, binary):
            errors.append(f"bad shape or domain for {name}")
    scalars = (
        "mutation_count",
        "mutation_cost",
        "exposure_cost",
        "top_two_energy",
        "secondary_cost",
        "total_cost",
        "_objective",
    )
    for name in scalars:
        if name not in solution or type(solution[name]) is not int:
            errors.append(f"bad scalar {name}")
    if errors:
        return errors

    selected = []
    for residue in range(residues):
        choices = [
            rotamer
            for rotamer in range(rotamers)
            if solution["select"][residue][rotamer] == 1
        ]
        if len(choices) != 1:
            errors.append("rotamer selection cardinality")
            selected.append(0)
            continue
        selected.append(choices[0])
        if not instance["valid"][residue][choices[0]]:
            errors.append("invalid rotamer selected")
    if errors:
        return errors

    expected_classes = [0] * classes
    total_charge = 0
    mutation_count = 0
    mutation_cost = 0
    exposure_cost = 0
    for residue, rotamer in enumerate(selected):
        expected_classes[instance["aa_class"][residue][rotamer] - 1] += 1
        total_charge += instance["charge"][residue][rotamer]
        mutation_count += int(rotamer + 1 != instance["native_rotamer"][residue])
        mutation_cost += instance["mutation_penalty"][residue][rotamer]
        exposure_cost += instance["exposure_penalty"][residue][rotamer]
    if solution["class_count"] != expected_classes:
        errors.append("class count audit")
    for cls, count in enumerate(expected_classes):
        if not (instance["class_min"][cls] <= count <= instance["class_max"][cls]):
            errors.append("class composition")
    if not (instance["charge_min"] <= total_charge <= instance["charge_max"]):
        errors.append("charge interval")
    if mutation_count > instance["mutation_budget"]:
        errors.append("mutation budget")

    for left in range(residues):
        for right in range(left + 1, residues):
            if instance["clash"][left][selected[left]][right][selected[right]]:
                errors.append("selected rotamers clash")

    chosen_bridges = [
        bridge for bridge, value in enumerate(solution["bridge"]) if value == 1
    ]
    if len(chosen_bridges) != instance["required_bridges"]:
        errors.append("required bridge count")
    endpoint_use = [0] * residues
    for bridge in chosen_bridges:
        left = instance["bridge_left"][bridge] - 1
        right = instance["bridge_right"][bridge] - 1
        endpoint_use[left] += 1
        endpoint_use[right] += 1
        if not instance["bridge_capable"][left][selected[left]]:
            errors.append("left bridge endpoint is not capable")
        if not instance["bridge_capable"][right][selected[right]]:
            errors.append("right bridge endpoint is not capable")
    if any(count > 1 for count in endpoint_use):
        errors.append("bridge matching")

    state_energy = []
    for state in range(states):
        energy = sum(
            instance["unary_energy"][state][residue][selected[residue]]
            for residue in range(residues)
        )
        energy += sum(
            instance["contact"][left][right]
            * instance["pair_energy"][state][left][selected[left]][right][
                selected[right]
            ]
            for left in range(residues)
            for right in range(left + 1, residues)
        )
        energy -= sum(
            instance["bridge_credit"][state][bridge] for bridge in chosen_bridges
        )
        state_energy.append(energy)
    if solution["state_energy"] != state_energy:
        errors.append("state energy audit")
    target = instance["target_state"] - 1
    for state in range(states):
        if state != target and (
            state_energy[target] + instance["stability_margin"][state]
            > state_energy[state]
        ):
            errors.append("multistate stability")

    top_two = sum(sorted(state_energy, reverse=True)[:2])
    secondary = (
        sum(state_energy)
        + instance["mutation_weight"] * mutation_cost
        + instance["exposure_weight"] * exposure_cost
    )
    total = instance["robust_weight"] * top_two + secondary
    audits = {
        "mutation_count": mutation_count,
        "mutation_cost": mutation_cost,
        "exposure_cost": exposure_cost,
        "top_two_energy": top_two,
        "secondary_cost": secondary,
        "total_cost": total,
        "_objective": total,
    }
    for name, value in audits.items():
        if solution[name] != value:
            errors.append(f"incorrect {name}")
    if total != expected:
        errors.append(f"suboptimal objective {total}, expected {expected}")
    return errors


def test_visible_design_is_feasible_and_optimal():
    """The visible certificate obeys every molecular rule and is globally optimal."""
    instance = json.loads((APP / "instance.json").read_text())
    assert not _validate(instance, _solve("visible"), RECEIPT["visible_objective"])


@pytest.mark.parametrize("item", RECEIPT["cases"], ids=lambda item: item["id"])
def test_hidden_design_family_generalizes(item):
    """Each held-out molecular instance is solved feasibly and optimally."""
    assert not _validate(item["instance"], _solve(item["id"]), item["objective"])
