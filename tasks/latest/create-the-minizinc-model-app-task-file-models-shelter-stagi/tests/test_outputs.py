import ast
import copy
import json
import os
import re
import subprocess
from pathlib import Path


APP = Path(os.environ.get("TASK_FILE_DIR", "/app/task_file"))
MODEL = APP / "models" / "shelter_staging.mzn"
RUNTIME_CASES = APP / "instances" / "runtime_cases.json"
PUBLIC_DZN = APP / "instances" / "public.dzn"


def load_public_dzn(path):
    """Parse the shipped, deliberately simple MiniZinc data surface."""
    assignments = dict(re.findall(r"\b([A-Za-z_]\w*)\s*=\s*(.*?);", path.read_text(), re.S))

    def value(name):
        raw = assignments[name].strip()
        if raw.startswith("[|"):
            rows = raw[2:-2].split("|")
            return [ast.literal_eval("[" + row.replace("true", "True").replace("false", "False") + "]") for row in rows]
        return ast.literal_eval(raw.replace("true", "True").replace("false", "False"))

    fields = (
        "P", "W", "Z", "T", "H", "pallet_count", "protection", "mandatory",
        "handling_class", "arrival_minute", "process_minutes", "deadline_minute",
        "zone_allowed", "team_allowed", "wave_capacity", "zone_capacity",
        "team_capacity", "parent", "min_scheduled", "max_scheduled", "min_cells",
        "class_changeover", "class_min_waves", "team_wave_limit",
    )
    instance = {name: value(name) for name in fields}
    assert value("C") == len(value("conflict_a")) == len(value("conflict_b"))
    instance["conflicts"] = list(zip(value("conflict_a"), value("conflict_b"), strict=True))
    return instance


PUBLIC = load_public_dzn(PUBLIC_DZN)


STRESS = {
    "P": 12, "W": 6, "Z": 4, "T": 3, "H": 4,
    "pallet_count": [3,4,2,5,3,2,4,3,2,5,3,2],
    "protection": [120,110,100,92,85,78,70,64,58,51,45,39],
    "mandatory": [True,True,False,False,False,False,False,False,False,False,False,False],
    "handling_class": [1,2,3,4,1,2,3,4,1,2,3,4],
    "arrival_minute": [0,0,3,6,9,12,15,18,21,24,27,30],
    "process_minutes": [7,8,6,9,5,7,8,6,9,5,7,8],
    "deadline_minute": [110,110,76,82,88,94,100,106,112,118,124,130],
    "zone_allowed": [[1,1,0,0],[0,1,1,0],[0,0,1,1],[1,0,0,1],[1,1,0,0],[0,1,1,0],[0,0,1,1],[1,0,0,1],[1,1,1,0],[0,1,1,1],[1,0,1,1],[1,1,0,1]],
    "team_allowed": [[1,0,0],[0,1,0],[0,0,1],[1,1,0],[0,1,1],[1,0,1],[1,1,0],[0,1,1],[1,0,1],[1,1,1],[1,1,1],[1,1,1]],
    "wave_capacity": [8,8,8,8,8,8], "zone_capacity": [11,11,11,11], "team_capacity": [15,15,15],
    "parent": [0,1,1,2,0,5,0,7,0,9,0,11], "conflicts": [(3,4),(5,6),(7,8),(9,10)],
    "min_scheduled": 8, "max_scheduled": 10, "min_cells": 8,
    "class_changeover": [[2,8,3,9],[6,2,7,4],[5,9,2,6],[3,7,8,2]],
    "class_min_waves": [1,1,1,1], "team_wave_limit": [4,4,4],
}


def mzn_bool(value):
    return "true" if value else "false"


def write_instance(path, instance):
    def array(values):
        return "[" + ",".join(map(str, values)) + "]"
    def matrix(rows):
        return "[|" + "|".join(",".join(mzn_bool(bool(v)) for v in row) for row in rows) + "|]"
    conflicts = instance["conflicts"]
    text = (
        f"P={instance['P']}; W={instance['W']}; Z={instance['Z']}; T={instance['T']}; H={instance['H']};\n"
        f"pallet_count={array(instance['pallet_count'])}; protection={array(instance['protection'])};\n"
        f"mandatory=[{','.join(mzn_bool(v) for v in instance['mandatory'])}];\n"
        f"handling_class={array(instance['handling_class'])};\n"
        f"arrival_minute={array(instance['arrival_minute'])}; process_minutes={array(instance['process_minutes'])}; deadline_minute={array(instance['deadline_minute'])};\n"
        f"zone_allowed={matrix(instance['zone_allowed'])}; team_allowed={matrix(instance['team_allowed'])};\n"
        f"wave_capacity={array(instance['wave_capacity'])}; zone_capacity={array(instance['zone_capacity'])}; team_capacity={array(instance['team_capacity'])};\n"
        f"parent={array(instance['parent'])}; C={len(conflicts)}; conflict_a={array([a for a,_ in conflicts])}; conflict_b={array([b for _,b in conflicts])};\n"
        f"min_scheduled={instance['min_scheduled']}; max_scheduled={instance['max_scheduled']}; min_cells={instance['min_cells']};\n"
        f"class_changeover=[|{'|'.join(','.join(map(str, row)) for row in instance['class_changeover'])}|];\n"
        f"class_min_waves={array(instance['class_min_waves'])}; team_wave_limit={array(instance['team_wave_limit'])};\n"
    )
    path.write_text(text)


def solve(instance, tmp_path, data=None):
    if data is None:
        data = tmp_path / "instance.dzn"
        write_instance(data, instance)
    completed = subprocess.run(
        ["minizinc", "--solver", "gecode", "--time-limit", "20000", str(MODEL), str(data)],
        text=True, capture_output=True, check=True,
    )
    matches = re.findall(r"RESULT (\[[^\n]+?\])\|(\[[^\n]+?\])\|(\[[^\n]+?\])\|(-?\d+)", completed.stdout)
    assert matches, completed.stdout + completed.stderr
    wave, zone, team, objective = matches[-1]
    return ast.literal_eval(wave), ast.literal_eval(zone), ast.literal_eval(team), int(objective)


def validate(instance, result):
    wave, zone, team, objective = result
    p_count = instance["P"]
    assert len(wave) == len(zone) == len(team) == p_count
    scheduled = [w > 0 for w in wave]
    assert instance["min_scheduled"] <= sum(scheduled) <= instance["max_scheduled"]
    for p in range(p_count):
        assert scheduled[p] == (zone[p] > 0) == (team[p] > 0)
        if instance["mandatory"][p]:
            assert scheduled[p]
        if scheduled[p]:
            assert instance["zone_allowed"][p][zone[p]-1]
            assert instance["team_allowed"][p][team[p]-1]
            parent = instance["parent"][p]
            if parent:
                assert scheduled[parent-1] and wave[parent-1] <= wave[p]
    for dimension, values, capacities in (("wave",wave,instance["wave_capacity"]),("zone",zone,instance["zone_capacity"]),("team",team,instance["team_capacity"])):
        del dimension
        for index, capacity in enumerate(capacities, 1):
            assert sum(instance["pallet_count"][p] for p in range(p_count) if values[p] == index) <= capacity
    for left, right in instance["conflicts"]:
        if scheduled[left-1] and scheduled[right-1]:
            assert wave[left-1] != wave[right-1]
    assert len({(wave[p],team[p]) for p in range(p_count) if scheduled[p]}) >= instance["min_cells"]
    used_waves = sorted(set(w for w in wave if w))
    assert used_waves == list(range(1, max(used_waves) + 1))
    wave_class = {}
    for p in range(p_count):
        if scheduled[p]:
            wave_class.setdefault(wave[p], instance["handling_class"][p])
            assert wave_class[wave[p]] == instance["handling_class"][p]
    for handling_class, minimum in enumerate(instance["class_min_waves"], 1):
        assert sum(value == handling_class for value in wave_class.values()) >= minimum
    for team_index, limit in enumerate(instance["team_wave_limit"], 1):
        assert len({wave[p] for p in range(p_count) if scheduled[p] and team[p] == team_index}) <= limit
    setup = instance["class_changeover"][wave_class[1]-1][wave_class[1]-1]
    setup += sum(instance["class_changeover"][wave_class[w-1]-1][wave_class[w]-1] for w in used_waves[1:])
    previous_finish = 0
    for w in used_waves:
        members = [p for p in range(p_count) if wave[p] == w]
        transition = instance["class_changeover"][wave_class[w]-1][wave_class[w]-1] if w == 1 else instance["class_changeover"][wave_class[w-1]-1][wave_class[w]-1]
        start = max(max(instance["arrival_minute"][p] for p in members), transition if w == 1 else previous_finish + transition)
        previous_finish = start + max(instance["process_minutes"][p] for p in members)
        assert all(previous_finish <= instance["deadline_minute"][p] for p in members)
    makespan = previous_finish
    expected = 1000000 * sum(instance["protection"][p] for p in range(p_count) if scheduled[p]) + 10000 * sum(scheduled) - 100 * setup - makespan - sum(wave)
    assert objective == expected


class TestShelterStagingConstraintModel:
    def test_public_instance_is_optimal(self, tmp_path):
        """The shipped public.dzn itself reaches its independently checked optimum."""
        result = solve(PUBLIC, tmp_path, PUBLIC_DZN)
        validate(PUBLIC, result)
        assert result[3] == 485077809

    def test_stress_instance_is_optimal(self, tmp_path):
        """A larger four-class instance preserves every constraint and optimum."""
        result = solve(STRESS, tmp_path)
        validate(STRESS, result)
        assert result[3] == 828097895

    def test_capacity_and_value_mutation_is_not_hardcoded(self, tmp_path):
        """A runtime-mutated instance is solved from supplied values, not public constants."""
        cases = json.loads(RUNTIME_CASES.read_text())
        assert len(cases) >= 18
        for updates in cases:
            instance = copy.deepcopy(PUBLIC)
            for key, value in updates.items():
                if key != "name":
                    instance[key] = value
            result = solve(instance, tmp_path)
            validate(instance, result)
