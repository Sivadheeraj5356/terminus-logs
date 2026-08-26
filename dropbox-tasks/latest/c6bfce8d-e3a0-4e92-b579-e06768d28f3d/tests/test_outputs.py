"""Verifier for the offline DepotLock dependency resolver task."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


APP = Path("/app")
PUBLIC_INDEX = APP / "fixtures/public/index.json"
PUBLIC_PROJECT = APP / "fixtures/public/project.json"
EXPECTED_PUBLIC_HASHES = {
    "index.json": "8722d270d98cfaca295222a2132003b1dac5fb78317968f7e5ce46b389c6f252",
    "project.json": "e79345f1897b967b1bad3b5ce7df89952617ec5b5235ff5bd38bdc293451b444",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_version(raw: str) -> tuple[int, int, int]:
    parts = raw.split(".")
    assert len(parts) == 3
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def satisfies(version: str, constraint: str) -> bool:
    constraint = constraint.strip()
    if constraint in {"", "*"}:
        return True
    current = parse_version(version)
    for part in [piece.strip() for piece in constraint.split(",") if piece.strip()]:
        if part == "*":
            continue
        if part.startswith("^"):
            base = parse_version(part[1:])
            if base[0] > 0:
                upper = (base[0] + 1, 0, 0)
            elif base[1] > 0:
                upper = (0, base[1] + 1, 0)
            else:
                upper = (0, 0, base[2] + 1)
            if not (current >= base and current < upper):
                return False
            continue
        op = ""
        raw = part
        for candidate in (">=", "<=", ">", "<"):
            if part.startswith(candidate):
                op = candidate
                raw = part[len(candidate) :].strip()
                break
        other = parse_version(raw)
        if op == "" and current != other:
            return False
        if op == ">=" and current < other:
            return False
        if op == ">" and current <= other:
            return False
        if op == "<=" and current > other:
            return False
        if op == "<" and current >= other:
            return False
    return True


def default_on(item: dict) -> bool:
    return item.get("default_features", True)


def target_matches(dep: dict, target: str) -> bool:
    targets = dep.get("targets") or ["*"]
    return "*" in targets or target in targets


def add(mapping: dict[str, set[str]], key: str, value: str) -> bool:
    bucket = mapping.setdefault(key, set())
    before = len(bucket)
    bucket.add(value)
    return len(bucket) != before


def expand_features(name: str, version_data: dict, initial: set[str]) -> tuple[set[str], set[str], set[str]]:
    features: set[str] = set()
    activated: set[str] = set()
    problems: set[str] = set()
    queue = sorted(initial)
    feature_table = version_data.get("features") or {}
    while queue:
        feature = queue.pop(0)
        if feature in features:
            continue
        if feature not in feature_table:
            problems.add(f"missing-feature:{name}:{feature}")
            continue
        features.add(feature)
        for atom in feature_table[feature]:
            if atom.startswith("dep:"):
                activated.add(atom[4:])
            elif atom not in features:
                queue.append(atom)
                queue.sort()
    return features, activated, problems


def candidate_versions(index: dict, name: str, constraints: set[str], patches: dict[str, str]) -> list[dict]:
    versions = index["packages"].get(name, [])
    patch = patches.get(name)
    if patch:
        return [
            candidate
            for candidate in versions
            if candidate["version"] == patch
            and all(satisfies(patch, constraint) for constraint in constraints)
        ]
    allowed = [
        candidate
        for candidate in versions
        if not candidate.get("yanked", False)
        and all(satisfies(candidate["version"], constraint) for constraint in constraints)
    ]
    return sorted(allowed, key=lambda item: parse_version(item["version"]), reverse=True)


def compute_closure(project: dict, selected: dict[str, dict]) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, list[str]], set[str]]:
    constraints: dict[str, set[str]] = {}
    requests: dict[str, set[str]] = {}
    active_deps: dict[str, list[str]] = {}
    problems: set[str] = set()
    for root in project["roots"]:
        add(constraints, root["name"], root["constraint"])
        if default_on(root):
            add(requests, root["name"], "default")
        for feature in root.get("features", []):
            add(requests, root["name"], feature)

    changed = True
    while changed:
        changed = False
        for name in sorted(selected):
            if name not in constraints:
                continue
            expanded, activated, feature_problems = expand_features(
                name, selected[name], requests.get(name, set())
            )
            problems.update(feature_problems)
            for feature in expanded:
                changed |= add(requests, name, feature)
            deps: list[str] = []
            for dep in selected[name].get("dependencies", []):
                if not target_matches(dep, project["target"]):
                    continue
                if not all(feature in expanded for feature in dep.get("when_features", [])):
                    continue
                if dep.get("optional", False) and dep["name"] not in activated:
                    continue
                deps.append(dep["name"])
                changed |= add(constraints, dep["name"], dep["constraint"])
                if default_on(dep):
                    changed |= add(requests, dep["name"], "default")
                for feature in dep.get("features", []):
                    changed |= add(requests, dep["name"], feature)
            active_deps[name] = sorted(set(deps))
    return constraints, requests, active_deps, problems


def incompatibilities(selected: dict[str, dict], target: str) -> set[str]:
    problems: set[str] = set()
    for owner, version_data in selected.items():
        for conflict in version_data.get("conflicts", []):
            other = conflict["name"]
            if (
                other in selected
                and target_matches(conflict, target)
                and satisfies(selected[other]["version"], conflict["constraint"])
            ):
                endpoints = sorted([f"{owner}@{version_data['version']}", f"{other}@{selected[other]['version']}"])
                problems.add(f"incompatible:{endpoints[0]}:{endpoints[1]}")
    return problems


def topo(selected: dict[str, dict], active_deps: dict[str, list[str]]) -> tuple[list[str], set[str]]:
    remaining = set(selected)
    built: set[str] = set()
    order: list[str] = []
    while remaining:
        ready = sorted(
            name
            for name in remaining
            if all(dep not in selected or dep in built for dep in active_deps.get(name, []))
        )
        if not ready:
            return [], {f"cycle:{name}" for name in remaining}
        chosen = ready[0]
        remaining.remove(chosen)
        built.add(chosen)
        order.append(chosen)
    return order, set()


def reference_resolve(index: dict, project: dict) -> dict:
    patches = project.get("patches") or {}
    final_state: tuple[dict[str, dict], dict[str, set[str]], dict[str, list[str]], list[str]] | None = None
    root_names = sorted({root["name"] for root in project["roots"]})
    priority_names = root_names + sorted(name for name in index["packages"] if name not in set(root_names))

    def preference_key(selected: dict[str, dict]) -> tuple[tuple[int, int, int], ...]:
        absent = (-1, -1, -1)
        return tuple(parse_version(selected[name]["version"]) if name in selected else absent for name in priority_names)

    def search(selected: dict[str, dict]) -> tuple[bool, set[str]]:
        nonlocal final_state
        constraints, requests, active_deps, feature_problems = compute_closure(project, selected)

        rejection = set(feature_problems)
        for name, version_data in selected.items():
            if name not in constraints:
                continue
            allowed = candidate_versions(index, name, constraints[name], patches)
            if not any(item["version"] == version_data["version"] for item in allowed):
                rejection.add(f"no-version:{name}")
        rejection.update(incompatibilities(selected, project["target"]))
        if rejection:
            return False, rejection

        unresolved = sorted(name for name in constraints if name not in selected)
        if unresolved:
            name = unresolved[0]
            if name not in index["packages"]:
                return False, {f"missing-package:{name}", f"no-version:{name}"}
            candidates = candidate_versions(index, name, constraints[name], patches)
            if not candidates:
                return False, {f"no-version:{name}"}
            branch_problems: set[str] = set()
            any_solved = False
            for candidate in candidates:
                next_selected = dict(selected)
                next_selected[name] = candidate
                solved, problems = search(next_selected)
                if solved:
                    any_solved = True
                else:
                    branch_problems.update(problems)
            if any_solved:
                return True, set()
            return False, branch_problems

        order, cycle_problems = topo(selected, active_deps)
        if cycle_problems:
            return False, cycle_problems
        if final_state is None or preference_key(selected) > preference_key(final_state[0]):
            final_state = selected, requests, active_deps, order
        return True, set()

    solved, problems = search({})
    if not solved:
        return {"status": "conflict", "packages": [], "build_order": [], "problems": sorted(problems)}

    assert final_state is not None
    selected, requests, active_deps, order = final_state

    direct = {root["name"] for root in project["roots"]}
    packages = [
        {
            "name": name,
            "version": selected[name]["version"],
            "direct": name in direct,
            "features": sorted(requests.get(name, set())),
            "dependencies": active_deps.get(name, []),
        }
        for name in sorted(selected)
    ]
    return {"status": "ok", "packages": packages, "build_order": order, "problems": []}


def run_depotlock(
    tmp_path: Path,
    index: dict | Path,
    project: dict | Path,
    *,
    trace_policy: bool = False,
) -> dict:
    binary = tmp_path / "depotlock"
    build = subprocess.run(
        ["go", "build", "-o", str(binary), "./cmd/depotlock"],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert build.returncode == 0, build.stderr
    if isinstance(index, dict):
        index_path = tmp_path / "index.json"
        index_path.write_text(json.dumps(index), encoding="utf-8")
    else:
        index_path = index
    if isinstance(project, dict):
        project_path = tmp_path / "project.json"
        project_path.write_text(json.dumps(project), encoding="utf-8")
    else:
        project_path = project
    out_path = tmp_path / "lock.json"
    command = [str(binary), "--index", str(index_path), "--project", str(project_path), "--out", str(out_path)]
    trace_path = tmp_path / "process.trace"
    if trace_policy:
        command = ["strace", "-f", "-qq", "-e", "trace=execve,connect", "-o", str(trace_path), *command]
    result = subprocess.run(
        command,
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert out_path.exists(), "depotlock did not create the requested output file"
    if trace_policy:
        trace = trace_path.read_text(encoding="utf-8")
        assert trace.count("execve(") == 1, "depotlock executed a helper process"
        assert "connect(" not in trace, "depotlock attempted network access"
    return json.loads(out_path.read_text(encoding="utf-8"))


def assert_report_shape(report: dict) -> None:
    assert set(report) == {"status", "packages", "build_order", "problems"}
    assert report["status"] in {"ok", "conflict"}
    assert isinstance(report["packages"], list)
    assert isinstance(report["build_order"], list)
    assert isinstance(report["problems"], list)
    if report["status"] == "conflict":
        assert report["packages"] == []
        assert report["build_order"] == []
        assert report["problems"] == sorted(report["problems"])
    else:
        names = [row["name"] for row in report["packages"]]
        assert names == sorted(names)
        assert set(report["build_order"]) == set(names)
        for row in report["packages"]:
            assert set(row) == {"name", "version", "direct", "features", "dependencies"}
            assert row["features"] == sorted(row["features"])
            assert row["dependencies"] == sorted(row["dependencies"])


def test_public_fixture_is_unchanged() -> None:
    """Verify the public index and project fixtures have not been edited to match a shortcut solution."""
    assert sha256(PUBLIC_INDEX) == EXPECTED_PUBLIC_HASHES["index.json"]
    assert sha256(PUBLIC_PROJECT) == EXPECTED_PUBLIC_HASHES["project.json"]


def test_go_artifact_uses_only_the_module_and_obeys_runtime_policy(tmp_path: Path) -> None:
    """Verify the Go artifact has no extra modules, helper executions, or network attempts."""
    module_check = subprocess.run(
        ["go", "list", "-m", "all"],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert module_check.returncode == 0, module_check.stderr
    assert module_check.stdout.strip().splitlines() == ["depotlock"]
    actual = run_depotlock(tmp_path, PUBLIC_INDEX, PUBLIC_PROJECT, trace_policy=True)
    assert actual == reference_resolve(
        json.loads(PUBLIC_INDEX.read_text(encoding="utf-8")),
        json.loads(PUBLIC_PROJECT.read_text(encoding="utf-8")),
    )


def test_public_fixture_resolves_to_reference_report(tmp_path: Path) -> None:
    """Verify the shipped fixture resolves exactly according to the documented resolver contract."""
    index = json.loads(PUBLIC_INDEX.read_text(encoding="utf-8"))
    project = json.loads(PUBLIC_PROJECT.read_text(encoding="utf-8"))
    actual = run_depotlock(tmp_path, PUBLIC_INDEX, PUBLIC_PROJECT)
    expected = reference_resolve(index, project)
    assert_report_shape(actual)
    assert actual == expected


def test_generated_patch_can_select_yanked_version_and_expand_features(tmp_path: Path) -> None:
    """Verify patches, yanked versions, default features, and transitive feature atoms interact correctly."""
    index = {
        "packages": {
            "tool": [
                {
                    "version": "1.2.0",
                    "features": {"default": ["cli"], "cli": ["dep:parser"]},
                    "dependencies": [
                        {"name": "core", "constraint": "^2.0.0"},
                        {"name": "parser", "constraint": "^0.3.0", "optional": True, "default_features": False},
                    ],
                }
            ],
            "core": [
                {
                    "version": "2.0.1",
                    "yanked": True,
                    "features": {"default": ["trace"], "trace": []},
                    "dependencies": [],
                },
                {"version": "2.0.0", "features": {"default": []}, "dependencies": []},
            ],
            "parser": [
                {"version": "0.3.4", "features": {"default": ["unicode"], "unicode": []}, "dependencies": []}
            ],
        }
    }
    project = {
        "target": "linux-amd64",
        "roots": [{"name": "tool", "constraint": "^1.0.0"}],
        "patches": {"core": "2.0.1"},
    }
    actual = run_depotlock(tmp_path, index, project)
    assert_report_shape(actual)
    assert actual == reference_resolve(index, project)
    assert next(row for row in actual["packages"] if row["name"] == "core")["version"] == "2.0.1"


def test_generated_target_gates_and_version_backtracking(tmp_path: Path) -> None:
    """Verify target-specific dependencies and combined constraints can force a lower compatible version."""
    index = {
        "packages": {
            "shell": [
                {
                    "version": "3.0.0",
                    "features": {"default": ["ssl"], "ssl": ["dep:openssl"], "json": []},
                    "dependencies": [
                        {"name": "lib", "constraint": ">=1.0.0,<2.0.0", "features": ["json"]},
                        {"name": "openssl", "constraint": "^1.1.0", "optional": True, "targets": ["linux-amd64"]},
                    ],
                }
            ],
            "addon": [
                {
                    "version": "1.0.0",
                    "features": {"default": []},
                    "dependencies": [{"name": "lib", "constraint": "<1.5.0", "default_features": False}],
                }
            ],
            "lib": [
                {"version": "1.8.0", "features": {"default": ["fast"], "fast": [], "json": []}, "dependencies": []},
                {"version": "1.4.9", "features": {"default": ["fast"], "fast": [], "json": []}, "dependencies": []},
            ],
            "openssl": [
                {"version": "1.1.9", "features": {"default": []}, "dependencies": []}
            ],
        }
    }
    project = {
        "target": "darwin-arm64",
        "roots": [
            {"name": "shell", "constraint": "^3.0.0"},
            {"name": "addon", "constraint": "1.0.0", "default_features": False},
        ],
    }
    actual = run_depotlock(tmp_path, index, project)
    assert_report_shape(actual)
    assert actual == reference_resolve(index, project)
    names = {row["name"] for row in actual["packages"]}
    assert "openssl" not in names
    assert next(row for row in actual["packages"] if row["name"] == "lib")["version"] == "1.4.9"


def test_missing_feature_rejects_a_partial_assignment_before_deeper_choices(tmp_path: Path) -> None:
    """A terminal feature error rejects its branch before an unresolved dependency is selected."""
    index = {
        "packages": {
            "app": [
                {
                    "version": "1.0.0",
                    "features": {"default": [], "broken": ["dep:ghost"]},
                    "dependencies": [{"name": "lib", "constraint": "^2.0.0"}],
                }
            ],
            "lib": [
                {"version": "2.1.0", "features": {"default": []}, "dependencies": []}
            ],
        }
    }
    project = {
        "target": "linux-amd64",
        "roots": [{"name": "app", "constraint": "1.0.0", "features": ["missing"]}],
        "patches": {"lib": "1.5.0"},
    }
    actual = run_depotlock(tmp_path, index, project)
    assert_report_shape(actual)
    assert actual == reference_resolve(index, project)
    assert actual["status"] == "conflict"
    assert actual["problems"] == ["missing-feature:app:missing"]


def test_generated_cycle_uses_dependency_first_ordering_or_conflict(tmp_path: Path) -> None:
    """Verify dependency-first topological sorting and cycle detection use deterministic package-name ordering."""
    ok_index = {
        "packages": {
            "root": [
                {
                    "version": "1.0.0",
                    "features": {"default": []},
                    "dependencies": [
                        {"name": "b", "constraint": "1.0.0"},
                        {"name": "a", "constraint": "1.0.0"},
                    ],
                }
            ],
            "a": [{"version": "1.0.0", "features": {"default": []}, "dependencies": []}],
            "b": [{"version": "1.0.0", "features": {"default": []}, "dependencies": []}],
        }
    }
    ok_project = {"target": "linux-amd64", "roots": [{"name": "root", "constraint": "1.0.0"}]}
    ok_actual = run_depotlock(tmp_path, ok_index, ok_project)
    assert ok_actual == reference_resolve(ok_index, ok_project)
    assert ok_actual["build_order"] == ["a", "b", "root"]

    cycle_index = {
        "packages": {
            "a": [
                {
                    "version": "1.0.0",
                    "features": {"default": []},
                    "dependencies": [{"name": "b", "constraint": "1.0.0"}],
                }
            ],
            "b": [
                {
                    "version": "1.0.0",
                    "features": {"default": []},
                    "dependencies": [{"name": "a", "constraint": "1.0.0"}],
                }
            ],
        }
    }
    cycle_project = {"target": "linux-amd64", "roots": [{"name": "a", "constraint": "1.0.0"}]}
    cycle_actual = run_depotlock(tmp_path, cycle_index, cycle_project)
    assert_report_shape(cycle_actual)
    assert cycle_actual == reference_resolve(cycle_index, cycle_project)
    assert cycle_actual["status"] == "conflict"
    assert cycle_actual["problems"] == ["cycle:a", "cycle:b"]


def test_generated_optional_dependency_is_ignored_until_feature_activates_it(tmp_path: Path) -> None:
    """Verify optional dependencies do not create constraints or missing-package problems until a feature activates them."""
    index = {
        "packages": {
            "runner": [
                {
                    "version": "1.0.0",
                    "features": {"default": [], "cloud": ["dep:cloud-sdk"]},
                    "dependencies": [
                        {"name": "base", "constraint": "1.0.0"},
                        {"name": "cloud-sdk", "constraint": "^4.0.0", "optional": True},
                    ],
                }
            ],
            "base": [{"version": "1.0.0", "features": {"default": []}, "dependencies": []}],
        }
    }
    inactive_project = {
        "target": "linux-amd64",
        "roots": [{"name": "runner", "constraint": "1.0.0", "default_features": False}],
    }
    inactive_actual = run_depotlock(tmp_path, index, inactive_project)
    assert_report_shape(inactive_actual)
    assert inactive_actual == reference_resolve(index, inactive_project)
    assert inactive_actual["status"] == "ok"
    assert {row["name"] for row in inactive_actual["packages"]} == {"base", "runner"}

    active_project = {
        "target": "linux-amd64",
        "roots": [
            {
                "name": "runner",
                "constraint": "1.0.0",
                "features": ["cloud"],
                "default_features": False,
            }
        ],
    }
    active_actual = run_depotlock(tmp_path, index, active_project)
    assert_report_shape(active_actual)
    assert active_actual == reference_resolve(index, active_project)
    assert active_actual["status"] == "conflict"
    assert active_actual["problems"] == ["missing-package:cloud-sdk", "no-version:cloud-sdk"]


def test_generated_caret_zero_ranges_and_patch_constraints(tmp_path: Path) -> None:
    """Verify caret ranges for 0.x versions and patch versions are still constrained by active requirements."""
    index = {
        "packages": {
            "app": [
                {
                    "version": "1.0.0",
                    "features": {"default": []},
                    "dependencies": [{"name": "lib", "constraint": "^0.2.3"}],
                }
            ],
            "lib": [
                {"version": "0.3.0", "features": {"default": []}, "dependencies": []},
                {"version": "0.2.9", "features": {"default": []}, "dependencies": []},
                {"version": "0.2.4", "features": {"default": []}, "dependencies": []},
            ],
        }
    }
    project = {"target": "linux-amd64", "roots": [{"name": "app", "constraint": "1.0.0"}]}
    actual = run_depotlock(tmp_path, index, project)
    assert_report_shape(actual)
    assert actual == reference_resolve(index, project)
    assert next(row for row in actual["packages"] if row["name"] == "lib")["version"] == "0.2.9"

    patched_project = {
        "target": "linux-amd64",
        "roots": [{"name": "app", "constraint": "1.0.0"}],
        "patches": {"lib": "0.3.0"},
    }
    patched_actual = run_depotlock(tmp_path, index, patched_project)
    assert_report_shape(patched_actual)
    assert patched_actual == reference_resolve(index, patched_project)
    assert patched_actual["status"] == "conflict"
    assert patched_actual["problems"] == ["no-version:lib"]


def test_generated_feature_union_from_multiple_dependents(tmp_path: Path) -> None:
    """Verify features requested through different dependency paths are unioned on the selected package."""
    index = {
        "packages": {
            "app": [
                {
                    "version": "1.0.0",
                    "features": {"default": []},
                    "dependencies": [
                        {"name": "exporter", "constraint": "1.0.0"},
                        {"name": "viewer", "constraint": "1.0.0"},
                    ],
                }
            ],
            "exporter": [
                {
                    "version": "1.0.0",
                    "features": {"default": []},
                    "dependencies": [
                        {
                            "name": "format",
                            "constraint": ">=2.0.0,<3.0.0",
                            "features": ["json"],
                            "default_features": False,
                        }
                    ],
                }
            ],
            "viewer": [
                {
                    "version": "1.0.0",
                    "features": {"default": []},
                    "dependencies": [
                        {
                            "name": "format",
                            "constraint": "^2.1.0",
                            "features": ["pretty"],
                            "default_features": True,
                        }
                    ],
                }
            ],
            "format": [
                {
                    "version": "2.2.0",
                    "features": {
                        "default": ["unicode"],
                        "json": ["dep:serde"],
                        "pretty": [],
                        "unicode": [],
                    },
                    "dependencies": [
                        {"name": "serde", "constraint": "^1.0.0", "optional": True}
                    ],
                }
            ],
            "serde": [{"version": "1.0.8", "features": {"default": []}, "dependencies": []}],
        }
    }
    project = {"target": "linux-amd64", "roots": [{"name": "app", "constraint": "1.0.0"}]}
    actual = run_depotlock(tmp_path, index, project)
    assert_report_shape(actual)
    assert actual == reference_resolve(index, project)
    format_row = next(row for row in actual["packages"] if row["name"] == "format")
    assert format_row["features"] == ["default", "json", "pretty", "unicode"]
    assert format_row["dependencies"] == ["serde"]


def test_global_search_backtracks_across_version_dependent_constraints(tmp_path: Path) -> None:
    """The highest root release becomes impossible only after a later root contributes another constraint."""
    index = {
        "packages": {
            "app": [
                {"version": "3.0.0", "features": {"default": []}, "dependencies": [{"name": "engine", "constraint": "^3.0.0"}]},
                {"version": "2.5.0", "features": {"default": []}, "dependencies": [{"name": "engine", "constraint": "^2.0.0"}]},
            ],
            "engine": [
                {"version": "3.1.0", "features": {"default": []}, "dependencies": []},
                {"version": "2.9.0", "features": {"default": []}, "dependencies": []},
            ],
            "tool": [{"version": "1.0.0", "features": {"default": []}, "dependencies": [{"name": "engine", "constraint": "^2.0.0"}]}],
        }
    }
    project = {"target": "linux-amd64", "roots": [{"name": "app", "constraint": "*"}, {"name": "tool", "constraint": "1.0.0"}]}
    actual = run_depotlock(tmp_path, index, project)
    assert actual == reference_resolve(index, project)
    versions = {row["name"]: row["version"] for row in actual["packages"]}
    assert versions == {"app": "2.5.0", "engine": "2.9.0", "tool": "1.0.0"}


def test_feature_availability_guards_and_cycles_force_lower_candidates(tmp_path: Path) -> None:
    """Requested features and a feature-gated cycle are candidate validity conditions, not post-resolution errors."""
    index = {
        "packages": {
            "app": [{
                "version": "1.0.0",
                "features": {"default": ["audit"], "audit": []},
                "dependencies": [
                    {"name": "adapter", "constraint": "*", "features": ["tls"], "default_features": False},
                    {"name": "router", "constraint": "*", "when_features": ["audit"]},
                ],
            }],
            "adapter": [
                {"version": "2.0.0", "features": {"default": []}, "dependencies": []},
                {"version": "1.8.0", "features": {"default": [], "tls": []}, "dependencies": []},
            ],
            "router": [
                {"version": "2.0.0", "features": {"default": []}, "dependencies": [{"name": "app", "constraint": "1.0.0"}]},
                {"version": "1.0.0", "features": {"default": []}, "dependencies": []},
            ],
        }
    }
    project = {"target": "linux-amd64", "roots": [{"name": "app", "constraint": "1.0.0"}]}
    actual = run_depotlock(tmp_path, index, project)
    assert actual == reference_resolve(index, project)
    versions = {row["name"]: row["version"] for row in actual["packages"]}
    assert versions["adapter"] == "1.8.0"
    assert versions["router"] == "1.0.0"


def test_version_conflicts_backtrack_and_failed_search_unions_terminal_reasons(tmp_path: Path) -> None:
    """Version incompatibilities participate in search, and all exhausted terminal reasons remain deterministic."""
    index = {
        "packages": {
            "a": [
                {"version": "2.0.0", "features": {"default": [], "x": []}, "dependencies": [], "conflicts": [{"name": "b", "constraint": "1.0.0"}]},
                {"version": "1.0.0", "features": {"default": []}, "dependencies": []},
            ],
            "b": [{"version": "1.0.0", "features": {"default": []}, "dependencies": []}],
        }
    }
    project = {
        "target": "linux-amd64",
        "roots": [
            {"name": "a", "constraint": "*", "features": ["x"], "default_features": False},
            {"name": "b", "constraint": "1.0.0"},
        ],
    }
    actual = run_depotlock(tmp_path, index, project)
    assert actual == reference_resolve(index, project)
    assert actual == {
        "status": "conflict",
        "packages": [],
        "build_order": [],
        "problems": ["incompatible:a@2.0.0:b@1.0.0", "missing-feature:a:x"],
    }


def test_input_order_unknown_fields_repeated_roots_and_declaration_union(tmp_path: Path) -> None:
    """Equivalent reordered inputs retain repeated-root and repeated-declaration union semantics."""
    index = {
        "ignored_index_field": {"anything": True},
        "packages": {
            "app": [{
                "version": "1.0.0",
                "features": {"default": [], "left": ["bridge"], "bridge": [], "right": ["dep:plug"]},
                "dependencies": [
                    {"name": "lib", "constraint": ">=1.0.0,<3.0.0", "features": ["alpha"], "default_features": False},
                    {"name": "lib", "constraint": "<2.0.0", "features": ["beta"]},
                    {"name": "plug", "constraint": "1.0.0", "optional": True, "default_features": False},
                ],
                "unknown_version_field": "ignored",
            }],
            "lib": [
                {"version": "2.5.0", "features": {"default": [], "alpha": [], "beta": []}, "dependencies": []},
                {"version": "1.7.0", "features": {"default": [], "alpha": [], "beta": []}, "dependencies": []},
            ],
            "plug": [{"version": "1.0.0", "features": {"default": []}, "dependencies": []}],
        },
    }
    project = {
        "target": "linux-amd64",
        "roots": [
            {"name": "app", "constraint": ">=1.0.0", "features": ["left"], "default_features": False},
            {"name": "app", "constraint": "<2.0.0", "features": ["right"], "default_features": False},
        ],
        "unknown_project_field": [1, 2, 3],
    }
    reordered_index = json.loads(json.dumps(index))
    reordered_index["packages"] = dict(reversed(list(reordered_index["packages"].items())))
    reordered_index["packages"]["app"][0]["dependencies"].reverse()
    reordered_index["packages"]["lib"].reverse()
    reordered_project = json.loads(json.dumps(project))
    reordered_project["roots"].reverse()

    actual = run_depotlock(tmp_path, index, project)
    reordered = run_depotlock(tmp_path, reordered_index, reordered_project)
    assert actual == reordered == reference_resolve(index, project)
    rows = {row["name"]: row for row in actual["packages"]}
    assert rows["app"]["features"] == ["bridge", "left", "right"]
    assert rows["lib"]["version"] == "1.7.0"
    assert rows["lib"]["features"] == ["alpha", "beta", "default"]
    assert rows["plug"]["features"] == []


def test_arbitrarily_large_versions_and_all_range_boundaries(tmp_path: Path) -> None:
    """Large numeric components, leading zeroes, caret-zero, and strict/inclusive bounds compare numerically."""
    huge = "9" * 96
    next_huge = "1" + "0" * 96
    patch = "8" * 90
    index = {
        "packages": {
            "major": [
                {"version": f"{next_huge}.0.0", "features": {"default": []}, "dependencies": []},
                {"version": f"{huge}.7.1", "features": {"default": []}, "dependencies": []},
            ],
            "tiny": [
                {"version": f"0.0.{int(patch) + 1}", "features": {"default": []}, "dependencies": []},
                {"version": f"00.00.00{patch}", "features": {"default": []}, "dependencies": []},
            ],
            "bounded": [
                {"version": "1.0.3", "features": {"default": []}, "dependencies": []},
                {"version": "1.0.2", "features": {"default": []}, "dependencies": []},
                {"version": "1.0.0", "features": {"default": []}, "dependencies": []},
            ],
        }
    }
    project = {
        "target": "any",
        "roots": [
            {"name": "major", "constraint": f"^{huge}.2.3"},
            {"name": "tiny", "constraint": f"^0.0.{patch}"},
            {"name": "bounded", "constraint": "> 1.0.0, <= 1.0.2"},
        ],
    }
    actual = run_depotlock(tmp_path, index, project)
    assert actual == reference_resolve(index, project)
    versions = {row["name"]: row["version"] for row in actual["packages"]}
    assert versions == {"bounded": "1.0.2", "major": f"{huge}.7.1", "tiny": f"00.00.00{patch}"}


def test_yanked_release_unused_patch_and_unmatched_activation_atom(tmp_path: Path) -> None:
    """Unpatched yanked releases stay unavailable while unused patches and unmatched dep atoms are harmless."""
    index = {
        "packages": {
            "app": [{
                "version": "1.0.0",
                "features": {"default": ["dep:ghost"]},
                "dependencies": [{"name": "lib", "constraint": "*"}],
            }],
            "lib": [
                {"version": "2.0.0", "yanked": True, "features": {"default": []}, "dependencies": []},
                {"version": "1.9.0", "features": {"default": []}, "dependencies": []},
            ],
            "Lib": [{"version": "9.0.0", "features": {"default": []}, "dependencies": []}],
        }
    }
    project = {
        "target": "linux",
        "roots": [{"name": "app", "constraint": "1.0.0"}],
        "patches": {"unused": "99.0.0"},
    }
    actual = run_depotlock(tmp_path, index, project)
    assert actual == reference_resolve(index, project)
    assert actual["status"] == "ok"
    assert {row["name"]: row["version"] for row in actual["packages"]} == {"app": "1.0.0", "lib": "1.9.0"}
    assert actual["problems"] == []


def test_targeted_one_sided_conflict_is_ignored_or_additive(tmp_path: Path) -> None:
    """A one-sided conflict follows its target gate and accumulates with another terminal reason."""
    index = {
        "packages": {
            "a": [
                {"version": "2.0.0", "features": {"default": [], "x": []}, "dependencies": [], "conflicts": [{"name": "b", "constraint": "1.0.0", "targets": ["darwin"]}]},
                {"version": "1.0.0", "features": {"default": []}, "dependencies": []},
            ],
            "b": [{"version": "1.0.0", "features": {"default": []}, "dependencies": []}],
        }
    }
    roots = [
        {"name": "a", "constraint": "*", "features": ["x"], "default_features": False},
        {"name": "b", "constraint": "1.0.0"},
    ]
    linux = {"target": "linux", "roots": roots}
    darwin = {"target": "darwin", "roots": roots}
    linux_actual = run_depotlock(tmp_path, index, linux)
    darwin_actual = run_depotlock(tmp_path, index, darwin)
    assert linux_actual == reference_resolve(index, linux)
    assert next(row for row in linux_actual["packages"] if row["name"] == "a")["version"] == "2.0.0"
    assert darwin_actual == reference_resolve(index, darwin)
    assert darwin_actual["problems"] == ["incompatible:a@2.0.0:b@1.0.0", "missing-feature:a:x"]


def test_all_feature_guards_and_optional_declarations_form_one_closure(tmp_path: Path) -> None:
    """All feature guards must hold, and activated declarations union constraints and requested features."""
    index = {
        "packages": {
            "app": [{
                "version": "1.0.0",
                "features": {"default": ["audit", "dep:store"], "audit": [], "premium": []},
                "dependencies": [
                    {"name": "store", "constraint": ">=2.0.0,<4.0.0", "features": ["fast"], "optional": True, "when_features": ["audit", "premium"], "default_features": False},
                    {"name": "store", "constraint": "<3.0.0", "features": ["safe"], "optional": True, "targets": ["linux"]},
                ],
            }],
            "store": [
                {"version": "3.1.0", "features": {"default": [], "fast": [], "safe": []}, "dependencies": []},
                {"version": "2.8.0", "features": {"default": [], "fast": [], "safe": []}, "dependencies": []},
            ],
        }
    }
    premium = {"target": "linux", "roots": [{"name": "app", "constraint": "1.0.0", "features": ["premium"]}]}
    basic = {"target": "darwin", "roots": [{"name": "app", "constraint": "1.0.0"}]}
    premium_actual = run_depotlock(tmp_path, index, premium)
    basic_actual = run_depotlock(tmp_path, index, basic)
    assert premium_actual == reference_resolve(index, premium)
    store = next(row for row in premium_actual["packages"] if row["name"] == "store")
    assert store["version"] == "2.8.0"
    assert store["features"] == ["default", "fast", "safe"]
    assert basic_actual == reference_resolve(index, basic)
    assert {row["name"] for row in basic_actual["packages"]} == {"app"}


def test_complete_assignment_preference_can_reject_a_locally_newer_transitive_release(tmp_path: Path) -> None:
    """The complete root-first preference vector outranks a locally newer transitive version."""
    index = {
        "packages": {
            "app": [{"version": "1.0.0", "features": {"default": []}, "dependencies": [{"name": "z", "constraint": "*"}]}],
            "z": [
                {"version": "2.0.0", "features": {"default": []}, "dependencies": [{"name": "m", "constraint": "1.0.0"}]},
                {"version": "1.0.0", "features": {"default": []}, "dependencies": [{"name": "a", "constraint": "1.0.0"}]},
            ],
            "a": [{"version": "1.0.0", "features": {"default": []}, "dependencies": []}],
            "m": [{"version": "1.0.0", "features": {"default": []}, "dependencies": []}],
        }
    }
    project = {"target": "linux", "roots": [{"name": "app", "constraint": "1.0.0"}]}
    actual = run_depotlock(tmp_path, index, project)
    assert actual == reference_resolve(index, project)
    assert {row["name"]: row["version"] for row in actual["packages"]} == {"a": "1.0.0", "app": "1.0.0", "z": "1.0.0"}


def test_compatibility_matrix_varies_target_feature_patch_and_root_order(tmp_path: Path) -> None:
    """A compatibility matrix combines target, feature, patch, and ordering modes without hidden semantics."""
    index = {
        "packages": {
            "product": [{
                "version": "2.0.0",
                "features": {"default": [], "secure": ["dep:tls"]},
                "dependencies": [
                    {"name": "core", "constraint": ">=1.0.0,<3.0.0"},
                    {"name": "tls", "constraint": "^1.0.0", "optional": True, "targets": ["linux"]},
                ],
            }],
            "addon": [{"version": "1.0.0", "features": {"default": []}, "dependencies": [{"name": "core", "constraint": "<2.0.0"}]}],
            "core": [
                {"version": "2.4.0", "features": {"default": []}, "dependencies": []},
                {"version": "1.8.0", "features": {"default": []}, "dependencies": []},
            ],
            "tls": [{"version": "1.3.0", "features": {"default": []}, "dependencies": []}],
        }
    }
    for target in ("linux", "darwin"):
        for secure in (False, True):
            for addon in (False, True):
                roots = [{"name": "product", "constraint": "2.0.0", "features": ["secure"] if secure else []}]
                if addon:
                    roots.append({"name": "addon", "constraint": "1.0.0"})
                project = {"target": target, "roots": list(reversed(roots)), "patches": {"core": "1.8.0"} if addon else {}}
                actual = run_depotlock(tmp_path, index, project)
                assert actual == reference_resolve(index, project)
                names = {row["name"] for row in actual["packages"]}
                assert ("tls" in names) == (target == "linux" and secure)
                core = next(row for row in actual["packages"] if row["name"] == "core")
                assert core["version"] == ("1.8.0" if addon else "2.4.0")
