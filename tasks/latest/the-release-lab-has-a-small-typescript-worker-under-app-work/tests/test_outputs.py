"""Verifier for the OCI diffusion card worker output contract."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any

APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
WORKER = APP_ROOT / "worker"
DEFAULT_SPEC_DIR = WORKER / "fixtures" / "specs"
DEFAULT_CALIBRATION = WORKER / "fixtures" / "calibrations.json"
DEFAULT_OUTPUT = APP_ROOT / "output" / "diffusion-report.json"

STATUSES = {"converged", "noisy", "escaped"}
REASONS = {"parse_error", "schema_error", "range_error", "calibration_missing", "dependency_missing", "dependency_cycle", "superseded", "retention_excluded"}
TOP_LEVEL_KEYS = {"generated_at", "source", "experiments", "rejections", "summary"}
EXPERIMENT_KEYS = {
    "file",
    "id",
    "revision",
    "image_ref",
    "calibration",
    "walkers",
    "steps",
    "mean",
    "variance",
    "ci95",
    "escape_rate",
    "status",
    "risk_score",
    "dependency_risk",
    "dependencies",
    "dimensions",
}
DIMENSION_KEYS = {"name", "weight", "mean", "variance", "escape_rate"}
REJECTION_KEYS = {"file", "reason", "message"}
ADJUSTMENT_FIELDS = {"weightScale", "weightBias", "lowerShift", "upperShift"}
STATUS_RANK = {"converged": 0, "noisy": 1, "escaped": 2}


def _strip_comment(line: str) -> str:
    quote: str | None = None
    for idx, ch in enumerate(line):
        if ch in {'"', "'"} and (idx == 0 or line[idx - 1] != "\\"):
            quote = None if quote == ch else (quote or ch)
        if ch == "#" and quote is None:
            return line[:idx]
    return line


def _scalar(text: str) -> Any:
    value = text.strip()
    if value in {"", "null", "~"}:
        return None if value != "" else ""
    if value == "true":
        return True
    if value == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        if any(ch in value for ch in ".eE"):
            return float(value)
        return int(value)
    except ValueError:
        return value


def _split_key_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError("YAML line missing ':'")
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def parse_yaml_lite(text: str) -> Any:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.lstrip(" ")
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if content.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError("list item without list parent")
            rest = content[2:].strip()
            if not rest:
                obj: dict[str, Any] = {}
                parent.append(obj)
                stack.append((indent, obj))
            elif ":" in rest:
                key, value = _split_key_value(rest)
                obj = {}
                obj[key] = {} if value == "" else _scalar(value)
                parent.append(obj)
                stack.append((indent, obj[key] if value == "" else obj))
            else:
                parent.append(_scalar(rest))
            continue
        key, value = _split_key_value(content)
        if value == "":
            child: Any = [] if key in {"dimensions", "dependsOn"} else {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _scalar(value)
    return root


def load_card(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return parse_yaml_lite(text)


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def round6(value: float) -> float:
    scaled = value * 1_000_000
    if scaled >= 0:
        return math.floor(scaled + 0.5) / 1_000_000
    return math.ceil(scaled - 0.5) / 1_000_000


def normalize_image(image: str, digest: str | None) -> str:
    if not digest:
        return image
    last_slash = image.rfind("/")
    last_colon = image.rfind(":")
    base = image[:last_colon] if last_colon > last_slash else image
    return f"{base}@{digest}"


class ParkMiller:
    def __init__(self, seed: int):
        self.state = seed

    def uniform(self) -> float:
        self.state = (self.state * 48271) % 2147483647
        return self.state / 2147483647


def adjustment_is_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return all(key in ADJUSTMENT_FIELDS and is_finite_number(adjustment) for key, adjustment in value.items())


def retention_is_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if set(value) - {"maxExperiments", "riskWindow"}:
        return False
    return (
        is_int(value.get("maxExperiments"))
        and value["maxExperiments"] > 0
        and is_finite_number(value.get("riskWindow"))
        and value["riskWindow"] >= 0
    )


def raw_profile_is_valid(profile: Any) -> bool:
    if not isinstance(profile, dict):
        return False
    if "inherits" in profile and (not isinstance(profile["inherits"], str) or not profile["inherits"]):
        return False
    for field in ["driftScale", "volatilityScale", "driftBias", "confidenceK", "ciLimit", "escapeThreshold", "dependencyAttenuation"]:
        if field in profile and not is_finite_number(profile[field]):
            return False
    if "dimensionAdjustments" in profile:
        adjustments = profile["dimensionAdjustments"]
        if not isinstance(adjustments, dict):
            return False
        if not all(isinstance(name, str) and adjustment_is_valid(value) for name, value in adjustments.items()):
            return False
    if "retention" in profile and not retention_is_valid(profile["retention"]):
        return False
    return True


def merge_adjustments(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = {name: dict(values) for name, values in parent.items()}
    for name, values in child.items():
        base = dict(merged.get(name, {}))
        base.update(values)
        merged[name] = base
    return merged


def resolve_profile(calibrations: dict[str, Any], name: str, stack: tuple[str, ...] = ()) -> dict[str, Any] | None:
    profiles = calibrations.get("profiles")
    if not isinstance(profiles, dict) or name not in profiles or name in stack:
        return None
    raw = profiles[name]
    if not raw_profile_is_valid(raw):
        return None
    if "inherits" in raw:
        resolved = resolve_profile(calibrations, raw["inherits"], stack + (name,))
        if resolved is None:
            return None
        merged: dict[str, Any] = json.loads(json.dumps(resolved))
    else:
        merged = {}
    for field in ["driftScale", "volatilityScale", "driftBias", "confidenceK", "ciLimit", "escapeThreshold", "dependencyAttenuation"]:
        if field in raw:
            merged[field] = raw[field]
    if "dimensionAdjustments" in raw:
        merged["dimensionAdjustments"] = merge_adjustments(merged.get("dimensionAdjustments", {}), raw["dimensionAdjustments"])
    if "retention" in raw:
        retention = dict(merged.get("retention", {}))
        retention.update(raw["retention"])
        merged["retention"] = retention
    required = ["driftScale", "volatilityScale", "driftBias", "confidenceK", "ciLimit", "escapeThreshold", "dependencyAttenuation"]
    if not all(is_finite_number(merged.get(field)) for field in required):
        return None
    if not (0 <= float(merged["dependencyAttenuation"]) <= 1):
        return None
    if "dimensionAdjustments" in merged:
        if not isinstance(merged["dimensionAdjustments"], dict):
            return None
        if not all(adjustment_is_valid(value) for value in merged["dimensionAdjustments"].values()):
            return None
    if "retention" in merged and not retention_is_valid(merged["retention"]):
        return None
    return merged


def validate_card(card: Any, calibrations: dict[str, Any]) -> tuple[str | None, str | None]:
    if not isinstance(card, dict):
        return "schema_error", "card is not an object"
    spec = card.get("spec")
    meta = card.get("metadata")
    container = card.get("container")
    if card.get("apiVersion") != "diffusion.ops/v1" or card.get("kind") != "DiffusionExperiment":
        return "schema_error", "apiVersion or kind is not supported"
    if not isinstance(meta, dict) or not isinstance(meta.get("name"), str) or not meta["name"]:
        return "schema_error", "metadata.name is required"
    if "revision" in meta and not is_int(meta.get("revision")):
        return "schema_error", "metadata.revision must be an integer when present"
    if not isinstance(container, dict) or not isinstance(container.get("image"), str) or not container["image"]:
        return "schema_error", "container.image is required"
    if "digest" in container and not isinstance(container.get("digest"), str):
        return "schema_error", "container.digest must be a string when present"
    if not isinstance(spec, dict):
        return "schema_error", "spec is required"
    for field in ["seed", "walkers", "steps"]:
        if not is_int(spec.get(field)):
            return "schema_error", f"{field} must be an integer"
    for field in ["drift", "volatility"]:
        if not is_finite_number(spec.get(field)):
            return "schema_error", f"{field} must be numeric"
    if not isinstance(spec.get("calibrationRef"), str) or not spec["calibrationRef"]:
        return "schema_error", "calibrationRef is required"
    if "dependsOn" in spec:
        deps = spec.get("dependsOn")
        if (not isinstance(deps, list) or not all(isinstance(item, str) and item for item in deps)
                or len(set(deps)) != len(deps)):
            return "schema_error", "dependsOn must be an array of unique non-empty strings"
    dims = spec.get("dimensions")
    if not isinstance(dims, list) or not dims:
        return "schema_error", "dimensions must be a non-empty array"
    for dim in dims:
        if not isinstance(dim, dict) or not isinstance(dim.get("name"), str) or not dim["name"]:
            return "schema_error", "dimension.name is required"
        for field in ["weight", "lower", "upper"]:
            if not is_finite_number(dim.get(field)):
                return "schema_error", f"dimension.{field} must be numeric"
    if meta.get("revision", 0) < 0:
        return "range_error", "metadata.revision must be non-negative"
    if not (1 <= spec["seed"] <= 2147483646):
        return "range_error", "seed is outside the Park-Miller range"
    if spec["walkers"] <= 0 or spec["steps"] <= 0:
        return "range_error", "walkers and steps must be positive"
    if spec["volatility"] < 0:
        return "range_error", "volatility must be non-negative"
    for dim in dims:
        if not (float(dim["lower"]) < float(dim["upper"])):
            return "range_error", "dimension lower must be below upper"
    profile = resolve_profile(calibrations, spec["calibrationRef"])
    if profile is None:
        return "calibration_missing", "calibration profile is not registered or malformed"
    return None, None


def population(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return mean, variance


def apply_adjustment(weight: float, lower: float, upper: float, adjustment: dict[str, Any] | None) -> tuple[float, float, float]:
    if not adjustment:
        return weight, lower, upper
    weight = weight * float(adjustment.get("weightScale", 1)) + float(adjustment.get("weightBias", 0))
    lower = lower + float(adjustment.get("lowerShift", 0))
    upper = upper + float(adjustment.get("upperShift", 0))
    return weight, lower, upper


def effective_dimensions(card: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, float | str]]:
    adjustments = profile.get("dimensionAdjustments", {})
    dims = []
    for raw_dim in card["spec"]["dimensions"]:
        weight = float(raw_dim["weight"])
        lower = float(raw_dim["lower"])
        upper = float(raw_dim["upper"])
        weight, lower, upper = apply_adjustment(weight, lower, upper, adjustments.get("*"))
        weight, lower, upper = apply_adjustment(weight, lower, upper, adjustments.get(raw_dim["name"]))
        dims.append({"name": raw_dim["name"], "weight": weight, "lower": lower, "upper": upper})
    return sorted(dims, key=lambda d: str(d["name"]))


def simulate(card: dict[str, Any], profile: dict[str, Any], rel_file: str) -> dict[str, Any]:
    spec = card["spec"]
    dims = effective_dimensions(card, profile)
    walkers = spec["walkers"]
    steps = spec["steps"]
    drift = float(spec["drift"]) * float(profile["driftScale"]) + float(profile["driftBias"])
    volatility = float(spec["volatility"]) * float(profile["volatilityScale"])
    rng = ParkMiller(spec["seed"])
    scores: list[float] = []
    dim_positions: dict[str, list[float]] = {str(dim["name"]): [] for dim in dims}
    dim_escaped: dict[str, int] = {str(dim["name"]): 0 for dim in dims}
    escaped_walkers = 0
    for _ in range(walkers):
        positions = {str(dim["name"]): 0.0 for dim in dims}
        escaped = {str(dim["name"]): False for dim in dims}
        for _ in range(steps):
            for dim in dims:
                uniform = rng.uniform()
                name = str(dim["name"])
                delta = drift * float(dim["weight"]) + volatility * (uniform * 2 - 1) * abs(float(dim["weight"]))
                positions[name] += delta
                if positions[name] < float(dim["lower"]) or positions[name] > float(dim["upper"]):
                    escaped[name] = True
        if any(escaped.values()):
            escaped_walkers += 1
        scores.append(sum(positions.values()))
        for dim in dims:
            name = str(dim["name"])
            dim_positions[name].append(positions[name])
            if escaped[name]:
                dim_escaped[name] += 1
    mean, variance = population(scores)
    half = float(profile["confidenceK"]) * math.sqrt(variance / walkers)
    escape_rate = escaped_walkers / walkers
    status = "escaped" if escape_rate > float(profile["escapeThreshold"]) else (
        "noisy" if (2 * half) > float(profile["ciLimit"]) else "converged"
    )
    risk_score = round6(STATUS_RANK[status] * 100 + escape_rate * 50 + max(0, (2 * half) - float(profile["ciLimit"])) * 10 + abs(mean))
    dimensions = []
    for dim in dims:
        name = str(dim["name"])
        dim_mean, dim_variance = population(dim_positions[name])
        dimensions.append({
            "name": name,
            "weight": round6(float(dim["weight"])),
            "mean": round6(dim_mean),
            "variance": round6(dim_variance),
            "escape_rate": round6(dim_escaped[name] / walkers),
        })
    return {
        "file": rel_file,
        "id": card["metadata"]["name"],
        "revision": int(card["metadata"].get("revision", 0)),
        "image_ref": normalize_image(card["container"]["image"], card["container"].get("digest")),
        "calibration": spec["calibrationRef"],
        "walkers": walkers,
        "steps": steps,
        "mean": round6(mean),
        "variance": round6(variance),
        "ci95": [round6(mean - half), round6(mean + half)],
        "escape_rate": round6(escape_rate),
        "status": status,
        "risk_score": risk_score,
        "dependency_risk": risk_score,
        "dependencies": sorted(spec.get("dependsOn", [])),
        "dimensions": dimensions,
    }


def _find_cycle(candidate_map: dict[str, dict[str, Any]], rejected: set[str]) -> set[str]:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> set[str]:
        state[node] = 1
        stack.append(node)
        for dep in candidate_map[node]["dependencies"]:
            if dep in rejected or dep not in candidate_map:
                continue
            if state.get(dep) == 1:
                return set(stack[stack.index(dep):])
            if state.get(dep, 0) == 0:
                found = visit(dep)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return set()

    for name in sorted(candidate_map):
        if name not in rejected and state.get(name, 0) == 0:
            found = visit(name)
            if found:
                return found
    return set()


def apply_dependencies(
    candidates: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    rejections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_id.setdefault(candidate["id"], []).append(candidate)
    candidate_map = {name: rows[0] for name, rows in by_id.items() if len(rows) == 1}
    marks: dict[str, str] = {}
    for candidate in candidates:
        if candidate["id"] not in candidate_map:
            marks[candidate["id"]] = "dependency_missing"
        elif any(dep not in candidate_map for dep in candidate["dependencies"]):
            marks[candidate["id"]] = "dependency_missing"
    while True:
        changed = False
        rejected = set(marks)
        for name, candidate in candidate_map.items():
            if name not in marks and any(dep in rejected for dep in candidate["dependencies"]):
                marks[name] = "dependency_missing"
                changed = True
        cycle = _find_cycle(candidate_map, set(marks))
        if cycle:
            for name in cycle:
                if name not in marks:
                    marks[name] = "dependency_cycle"
                    changed = True
        if not changed:
            break
    survivors: list[dict[str, Any]] = []
    for candidate in candidates:
        reason = marks.get(candidate["id"])
        if reason:
            rejections.append({"file": candidate["file"], "reason": reason, "message": f"dependency graph rejected {candidate['id']}"})
        else:
            survivors.append(candidate)
    survivor_map = {candidate["id"]: candidate for candidate in survivors}
    visiting: set[str] = set()
    done: set[str] = set()

    def compute(name: str) -> None:
        if name in done:
            return
        visiting.add(name)
        row = survivor_map[name]
        for dep in row["dependencies"]:
            compute(dep)
        max_dep = max((float(survivor_map[dep]["dependency_risk"]) for dep in row["dependencies"]), default=0.0)
        attenuation = float(profiles[row["calibration"]]["dependencyAttenuation"])
        row["dependency_risk"] = round6(float(row["risk_score"]) + attenuation * max_dep)
        visiting.remove(name)
        done.add(name)

    for name in sorted(survivor_map):
        compute(name)
    return survivors


def reduce_candidates(candidates: list[dict[str, Any]], rejections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        groups.setdefault((candidate["image_ref"], candidate["calibration"]), []).append(candidate)
    retained: list[dict[str, Any]] = []
    for rows in groups.values():
        rows = sorted(rows, key=lambda row: (-float(row["dependency_risk"]), -int(row["revision"]), row["id"], row["file"]))
        winner = rows[0]
        retained.append(winner)
        for loser in rows[1:]:
            rejections.append({"file": loser["file"], "reason": "superseded", "message": f"superseded by {winner['file']}"})
    return retained


def apply_retention(
    experiments: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    rejections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for experiment in experiments:
        grouped.setdefault(experiment["calibration"], []).append(experiment)
    kept: list[dict[str, Any]] = []
    for calibration, rows in grouped.items():
        retention = profiles[calibration].get("retention")
        if not retention:
            kept.extend(rows)
            continue
        ordered = sorted(rows, key=lambda row: (-float(row["dependency_risk"]), -int(row["revision"]), row["id"], row["file"]))
        top_risk = float(ordered[0]["dependency_risk"])
        max_experiments = int(retention["maxExperiments"])
        risk_window = float(retention["riskWindow"])
        for idx, row in enumerate(ordered):
            if idx < max_experiments or top_risk - float(row["dependency_risk"]) <= risk_window:
                kept.append(row)
            else:
                rejections.append({
                    "file": row["file"],
                    "reason": "retention_excluded",
                    "message": f"excluded by retention policy for {calibration}",
                })
    return kept


def _js_number(value: int | float) -> str:
    if isinstance(value, bool):
        raise TypeError("boolean is not a JSON number")
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    text = f"{float(value):.6f}"
    return text.rstrip("0").rstrip(".")


def _stable_json(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _js_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_stable_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            json.dumps(key, ensure_ascii=False, separators=(",", ":")) + ":" + _stable_json(value[key])
            for key in sorted(value)
        ) + "}"
    raise TypeError(f"unsupported JSON value {value!r}")


def canonical_digest(experiments: list[dict[str, Any]], rejections: list[dict[str, Any]], status_counts: dict[str, int], calibrations: list[dict[str, Any]]) -> str:
    digest_rejections = [{"file": row["file"], "reason": row["reason"]} for row in rejections]
    payload = {
        "experiments": experiments,
        "rejections": digest_rejections,
        "status_counts": status_counts,
        "calibrations": calibrations,
    }
    return hashlib.sha256(_stable_json(payload).encode()).hexdigest()


def expected_report(spec_dir: Path, calibration: Path) -> dict[str, Any]:
    calibrations = json.loads(calibration.read_text(encoding="utf-8"))
    files = sorted(path for path in spec_dir.rglob("*") if path.suffix.lower() in {".json", ".yaml", ".yml"})
    candidates: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for path in files:
        rel = path.relative_to(spec_dir).as_posix()
        try:
            card = load_card(path)
        except Exception as exc:  # noqa: BLE001 - parse failures are part of contract
            rejections.append({"file": rel, "reason": "parse_error", "message": str(exc)})
            continue
        reason, message = validate_card(card, calibrations)
        if reason:
            rejections.append({"file": rel, "reason": reason, "message": message or reason})
            continue
        profile = resolve_profile(calibrations, card["spec"]["calibrationRef"])
        assert profile is not None
        candidates.append(simulate(card, profile, rel))
    resolved_profiles = {
        name: profile
        for name in {candidate["calibration"] for candidate in candidates}
        if (profile := resolve_profile(calibrations, name)) is not None
    }
    candidates = apply_dependencies(candidates, resolved_profiles, rejections)
    experiments = reduce_candidates(candidates, rejections)
    experiments = apply_retention(experiments, resolved_profiles, rejections)
    experiments.sort(key=lambda row: (row["image_ref"], row["id"]))
    rejections.sort(key=lambda row: row["file"])
    status_counts = {"converged": 0, "noisy": 0, "escaped": 0}
    for exp in experiments:
        status_counts[exp["status"]] += 1
    profile_names = sorted({exp["calibration"] for exp in experiments})
    calibration_rows = []
    for name in profile_names:
        rows = [exp for exp in experiments if exp["calibration"] == name]
        calibration_rows.append({
            "name": name,
            "experiments": len(rows),
            "mean_escape_rate": round6(sum(exp["escape_rate"] for exp in rows) / len(rows)),
            "mean_dependency_risk": round6(sum(exp["dependency_risk"] for exp in rows) / len(rows)),
        })
    digest = canonical_digest(experiments, rejections, status_counts, calibration_rows)
    return {
        "generated_at": "1970-01-01T00:00:00.000Z",
        "source": {
            "spec_dir": str(spec_dir),
            "calibration": str(calibration),
            "accepted": len(experiments),
            "rejected": len(rejections),
        },
        "experiments": experiments,
        "rejections": rejections,
        "summary": {
            "status_counts": status_counts,
            "calibrations": calibration_rows,
            "digest": digest,
        },
    }


def input_snapshot(spec_dir: Path, calibration: Path, output: Path) -> dict[str, str]:
    """Return stable content hashes for input cards and calibration before or after a run."""
    snapshot: dict[str, str] = {}
    try:
        ignored_output = output.resolve()
    except FileNotFoundError:
        ignored_output = output.absolute()
    for path in sorted(item for item in spec_dir.rglob("*") if item.is_file()):
        if path.resolve() == ignored_output:
            continue
        rel = path.relative_to(spec_dir).as_posix()
        snapshot[f"spec/{rel}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    snapshot["calibration"] = hashlib.sha256(calibration.read_bytes()).hexdigest()
    return snapshot


def run_report(
    spec_dir: Path = DEFAULT_SPEC_DIR,
    calibration: Path = DEFAULT_CALIBRATION,
    output: Path = DEFAULT_OUTPUT,
    *,
    expected_code: int = 0,
) -> dict[str, Any]:
    """Run the public npm command and return the parsed report while guarding inputs."""
    before_inputs = input_snapshot(spec_dir, calibration, output)
    if output.exists():
        output.unlink()
    result = subprocess.run(
        [
            "npm",
            "run",
            "report",
            "--",
            "--spec-dir",
            str(spec_dir),
            "--calibration",
            str(calibration),
            "--output",
            str(output),
        ],
        cwd=WORKER,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == expected_code, result.stdout + result.stderr
    assert input_snapshot(spec_dir, calibration, output) == before_inputs, "worker mutated input cards or calibration"
    assert output.exists(), "worker did not create the requested output file"
    return json.loads(output.read_text(encoding="utf-8"))


def assert_report_matches_expected(report: dict[str, Any], expected: dict[str, Any]) -> None:
    """Compare the behaviorally important report fields with the independent model."""
    assert report["generated_at"] == expected["generated_at"]
    assert report["source"] == expected["source"]
    assert report["experiments"] == expected["experiments"]
    assert [(row["file"], row["reason"]) for row in report["rejections"]] == [
        (row["file"], row["reason"]) for row in expected["rejections"]
    ]
    assert all(isinstance(row.get("message"), str) and row["message"] for row in report["rejections"])
    assert report["summary"]["status_counts"] == expected["summary"]["status_counts"]
    assert report["summary"]["calibrations"] == expected["summary"]["calibrations"]
    assert report["summary"]["digest"] == canonical_digest(
        report["experiments"],
        report["rejections"],
        report["summary"]["status_counts"],
        report["summary"]["calibrations"],
    )


def write_json(path: Path, data: Any) -> None:
    """Write deterministic JSON fixture data for dynamic verifier cases."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_yaml(path: Path, text: str) -> None:
    """Write small YAML fixture data for dynamic verifier cases."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_default_command_writes_complete_schema_and_types() -> None:
    """The documented command must emit the complete public JSON contract."""
    report = run_report()
    assert set(report) == TOP_LEVEL_KEYS
    assert report["generated_at"] == "1970-01-01T00:00:00.000Z"
    assert set(report["source"]) == {"spec_dir", "calibration", "accepted", "rejected"}
    assert isinstance(report["source"]["accepted"], int) and not isinstance(report["source"]["accepted"], bool)
    assert isinstance(report["source"]["rejected"], int) and not isinstance(report["source"]["rejected"], bool)
    assert report["source"]["accepted"] > 0
    assert set(report["summary"]["status_counts"]) == STATUSES
    assert all(isinstance(report["summary"]["status_counts"][key], int) and not isinstance(report["summary"]["status_counts"][key], bool) for key in STATUSES)
    assert isinstance(report["summary"]["digest"], str)
    assert len(report["summary"]["digest"]) == 64
    int(report["summary"]["digest"], 16)
    for row in report["summary"]["calibrations"]:
        assert set(row) == {"name", "experiments", "mean_escape_rate", "mean_dependency_risk"}
        assert isinstance(row["name"], str) and row["name"]
        assert isinstance(row["experiments"], int) and row["experiments"] > 0
        assert isinstance(row["mean_escape_rate"], (int, float)) and not isinstance(row["mean_escape_rate"], bool)
        assert isinstance(row["mean_dependency_risk"], (int, float)) and not isinstance(row["mean_dependency_risk"], bool)
    for exp in report["experiments"]:
        assert set(exp) == EXPERIMENT_KEYS
        assert exp["status"] in STATUSES
        assert isinstance(exp["file"], str) and exp["file"]
        assert isinstance(exp["id"], str) and exp["id"]
        assert isinstance(exp["revision"], int) and not isinstance(exp["revision"], bool) and exp["revision"] >= 0
        assert isinstance(exp["image_ref"], str) and exp["image_ref"]
        assert isinstance(exp["walkers"], int) and not isinstance(exp["walkers"], bool) and exp["walkers"] > 0
        assert isinstance(exp["steps"], int) and not isinstance(exp["steps"], bool) and exp["steps"] > 0
        assert isinstance(exp["mean"], (int, float)) and not isinstance(exp["mean"], bool)
        assert isinstance(exp["variance"], (int, float)) and not isinstance(exp["variance"], bool)
        assert isinstance(exp["risk_score"], (int, float)) and not isinstance(exp["risk_score"], bool)
        assert isinstance(exp["dependency_risk"], (int, float)) and not isinstance(exp["dependency_risk"], bool)
        assert isinstance(exp["dependencies"], list)
        assert all(isinstance(item, str) and item for item in exp["dependencies"])
        assert exp["dependencies"] == sorted(exp["dependencies"])
        assert isinstance(exp["ci95"], list) and len(exp["ci95"]) == 2
        assert isinstance(exp["escape_rate"], (int, float)) and not isinstance(exp["escape_rate"], bool)
        for dim in exp["dimensions"]:
            assert set(dim) == DIMENSION_KEYS
            assert isinstance(dim["name"], str) and dim["name"]
    for row in report["rejections"]:
        assert set(row) == REJECTION_KEYS
        assert row["reason"] in REASONS
        assert isinstance(row["message"], str) and row["message"]


def test_static_fixture_values_match_independent_model() -> None:
    """Static JSON/YAML cards must match an independent simulation and reduction model."""
    expected = expected_report(DEFAULT_SPEC_DIR, DEFAULT_CALIBRATION)
    report = run_report(output=APP_ROOT / "output" / "static-model-report.json")
    expected["source"]["spec_dir"] = str(DEFAULT_SPEC_DIR)
    expected["source"]["calibration"] = str(DEFAULT_CALIBRATION)
    assert_report_matches_expected(report, expected)


def test_mixed_inputs_and_rejection_reasons_are_accounted() -> None:
    """The default fixture set includes accepted cards plus validation, cohort, and retention rejections."""
    report = run_report(output=APP_ROOT / "output" / "rejection-report.json")
    assert report["source"]["accepted"] == 3
    assert report["source"]["rejected"] == 6
    assert {row["id"] for row in report["experiments"]} == {"alpha-service", "beta-worker", "gamma-canary"}
    reasons = {row["reason"] for row in report["rejections"]}
    assert reasons == {"parse_error", "schema_error", "range_error", "calibration_missing", "superseded", "retention_excluded"}
    assert {row["file"] for row in report["rejections"]} == {
        "alpha-shadow.yaml",
        "bad-json.json",
        "delta-stable.json",
        "missing-kind.yaml",
        "range-problem.json",
        "unknown-calibration.yaml",
    }


def test_ordering_and_digest_contract() -> None:
    """Experiment, rejection, dimension, summary ordering and digest must be deterministic."""
    report = run_report(output=APP_ROOT / "output" / "ordering-report.json")
    assert [(exp["image_ref"], exp["id"]) for exp in report["experiments"]] == sorted(
        (exp["image_ref"], exp["id"]) for exp in report["experiments"]
    )
    assert [row["file"] for row in report["rejections"]] == sorted(row["file"] for row in report["rejections"])
    for exp in report["experiments"]:
        assert [dim["name"] for dim in exp["dimensions"]] == sorted(dim["name"] for dim in exp["dimensions"])
    assert [row["name"] for row in report["summary"]["calibrations"]] == sorted(
        row["name"] for row in report["summary"]["calibrations"]
    )
    assert report["summary"]["digest"] == canonical_digest(
        report["experiments"],
        report["rejections"],
        report["summary"]["status_counts"],
        report["summary"]["calibrations"],
    )


def test_repeated_runs_are_byte_identical() -> None:
    """Running the same inputs twice must produce identical bytes."""
    out_a = APP_ROOT / "output" / "deterministic-a.json"
    out_b = APP_ROOT / "output" / "deterministic-b.json"
    run_report(output=out_a)
    run_report(output=out_b)
    assert out_a.read_bytes() == out_b.read_bytes()


def test_custom_paths_and_parent_output_directory(tmp_path: Path) -> None:
    """The worker must honor custom absolute paths and apply calibration dimension adjustments."""
    spec_dir = tmp_path / "cards"
    calibration = tmp_path / "calibration" / "profiles.json"
    output = tmp_path / "deep" / "nested" / "report.json"
    write_json(calibration, {
        "profiles": {
            "custom-profile": {
                "driftScale": 1.05,
                "volatilityScale": 0.65,
                "driftBias": 0.002,
                "confidenceK": 1.5,
                "ciLimit": 0.9,
                "escapeThreshold": 0.75,
                "dependencyAttenuation": 0.2,
                "dimensionAdjustments": {
                    "*": {"weightScale": 1.2, "lowerShift": -0.05},
                    "alpha": {"weightBias": -0.1, "upperShift": 0.08},
                },
            }
        }
    })
    write_json(spec_dir / "zeta.json", {
        "apiVersion": "diffusion.ops/v1",
        "kind": "DiffusionExperiment",
        "metadata": {"name": "fresh-json-731", "revision": 4},
        "container": {"image": "registry.example/fresh/zeta:7", "digest": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"},
        "spec": {
            "seed": 731,
            "walkers": 9,
            "steps": 5,
            "drift": 0.014,
            "volatility": 0.11,
            "calibrationRef": "custom-profile",
            "dimensions": [
                {"name": "omega", "weight": 0.45, "lower": -0.8, "upper": 0.8},
                {"name": "alpha", "weight": 1.05, "lower": -0.9, "upper": 0.95},
            ],
        },
    })
    expected = expected_report(spec_dir, calibration)
    report = run_report(spec_dir=spec_dir, calibration=calibration, output=output)
    assert output.exists()
    assert_report_matches_expected(report, expected)
    assert report["experiments"][0]["image_ref"] == normalize_image("registry.example/fresh/zeta:7", "sha" + "256:" + "d" * 64)
    assert {dim["name"]: dim["weight"] for dim in report["experiments"][0]["dimensions"]} == {"alpha": 1.16, "omega": 0.54}


def test_dynamic_variant_defeats_hardcoded_solution(tmp_path: Path) -> None:
    """Fresh IDs, profiles, duplicate cohorts, paths, and digest changes catch fixture-only reports."""
    default_digest = run_report(output=APP_ROOT / "output" / "baseline-digest.json")["summary"]["digest"]
    spec_dir = tmp_path / "variant-specs"
    calibration = tmp_path / "variant-calibrations.json"
    output = tmp_path / "variant-output" / "diffusion-report.json"
    write_json(calibration, {
        "profiles": {
            "fresh-base": {
                "driftScale": 0.82,
                "volatilityScale": 0.7,
                "driftBias": 0.004,
                "confidenceK": 1.96,
                "ciLimit": 0.5,
                "escapeThreshold": 0.4,
                "dependencyAttenuation": 0.22,
                "dimensionAdjustments": {"*": {"weightScale": 1.02, "lowerShift": -0.02}},
            },
            "fresh-stable": {
                "inherits": "fresh-base",
                "dimensionAdjustments": {"theta": {"weightBias": 0.03}},
            },
            "fresh-wide": {
                "inherits": "fresh-base",
                "driftScale": 1.25,
                "volatilityScale": 1.4,
                "driftBias": -0.003,
                "confidenceK": 1.8,
                "ciLimit": 0.55,
                "escapeThreshold": 0.3,
                "dependencyAttenuation": 0.18,
                "dimensionAdjustments": {"*": {"weightScale": 1.1}, "alpha": {"weightBias": 0.05}},
                "retention": {"maxExperiments": 1, "riskWindow": 0},
            },
            "cycle-a": {"inherits": "cycle-b"},
            "cycle-b": {"inherits": "cycle-a"},
        }
    })
    write_json(spec_dir / "a" / "nebula.json", {
        "apiVersion": "diffusion.ops/v1",
        "kind": "DiffusionExperiment",
        "metadata": {"name": "nebula-fresh-119", "revision": 1},
        "container": {"image": "registry.dynamic/nebula:119"},
        "spec": {
            "seed": 119,
            "walkers": 11,
            "steps": 8,
            "drift": 0.018,
            "volatility": 0.2,
            "calibrationRef": "fresh-wide",
            "dimensions": [
                {"name": "beta", "weight": -0.75, "lower": -0.85, "upper": 0.82},
                {"name": "alpha", "weight": 0.5, "lower": -0.7, "upper": 0.75},
            ],
        },
    })
    write_json(spec_dir / "a" / "nebula-low-risk.json", {
        "apiVersion": "diffusion.ops/v1",
        "kind": "DiffusionExperiment",
        "metadata": {"name": "nebula-low-risk-119", "revision": 99},
        "container": {"image": "registry.dynamic/nebula:119"},
        "spec": {
            "seed": 120,
            "walkers": 4,
            "steps": 2,
            "drift": 0.0,
            "volatility": 0.0,
            "calibrationRef": "fresh-wide",
            "dimensions": [{"name": "alpha", "weight": 0.2, "lower": -99, "upper": 99}],
        },
    })
    write_json(spec_dir / "a" / "orion-retained-out.json", {
        "apiVersion": "diffusion.ops/v1",
        "kind": "DiffusionExperiment",
        "metadata": {"name": "orion-retained-out-411", "revision": 2},
        "container": {"image": "registry.dynamic/orion:411"},
        "spec": {
            "seed": 411,
            "walkers": 5,
            "steps": 2,
            "drift": 0.0,
            "volatility": 0.0,
            "calibrationRef": "fresh-wide",
            "dimensions": [{"name": "alpha", "weight": 0.1, "lower": -50, "upper": 50}],
        },
    })
    write_yaml(spec_dir / "b" / "aurora.yaml", """
apiVersion: diffusion.ops/v1
kind: DiffusionExperiment
metadata:
  name: aurora-fresh-223
  revision: 3
container:
  image: registry.dynamic/team/aurora:223
  digest: sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
spec:
  seed: 223
  walkers: 10
  steps: 6
  drift: -0.01
  volatility: 0.16
  calibrationRef: fresh-stable
  dimensions:
    - name: theta
      weight: 1.2
      lower: -1.1
      upper: 1.2
    - name: eta
      weight: 0.8
      lower: -0.9
      upper: 0.85
""")
    write_yaml(spec_dir / "c" / "unknown.yaml", """
apiVersion: diffusion.ops/v1
kind: DiffusionExperiment
metadata:
  name: fresh-unknown
container:
  image: registry.dynamic/bad/unknown:1
spec:
  seed: 999
  walkers: 3
  steps: 2
  drift: 0.01
  volatility: 0.1
  calibrationRef: cycle-a
  dimensions:
    - name: x
      weight: 1.0
      lower: -1.0
      upper: 1.0
""")
    (spec_dir / "broken.json").write_text('{"apiVersion": "diffusion.ops/v1",', encoding="utf-8")
    expected = expected_report(spec_dir, calibration)
    report = run_report(spec_dir=spec_dir, calibration=calibration, output=output)
    assert_report_matches_expected(report, expected)
    assert {row["id"] for row in report["experiments"]} == {"nebula-fresh-119", "aurora-fresh-223"}
    assert report["summary"]["digest"] != default_digest
    assert {row["reason"] for row in report["rejections"]} == {"parse_error", "calibration_missing", "superseded", "retention_excluded"}


def test_no_accepted_cards_exit_two_but_still_write_report(tmp_path: Path) -> None:
    """All-invalid input is a documented non-success exit that still produces a report."""
    spec_dir = tmp_path / "invalid-only"
    calibration = tmp_path / "cal.json"
    output = tmp_path / "report.json"
    write_json(calibration, {"profiles": {"p": {"driftScale": 1, "volatilityScale": 1, "driftBias": 0, "confidenceK": 1.96, "ciLimit": 1, "escapeThreshold": 1, "dependencyAttenuation": 0}}})
    write_json(spec_dir / "bad-range.json", {
        "apiVersion": "diffusion.ops/v1",
        "kind": "DiffusionExperiment",
        "metadata": {"name": "bad-range", "revision": -1},
        "container": {"image": "registry.invalid/range:0"},
        "spec": {
            "seed": 0,
            "walkers": 2,
            "steps": 2,
            "drift": 0.1,
            "volatility": 0.1,
            "calibrationRef": "p",
            "dimensions": [{"name": "x", "weight": 1, "lower": -1, "upper": 1}],
        },
    })
    (spec_dir / "parse.yaml").write_text("- stray", encoding="utf-8")
    expected = expected_report(spec_dir, calibration)
    report = run_report(spec_dir=spec_dir, calibration=calibration, output=output, expected_code=2)
    assert report["source"]["accepted"] == 0
    assert report["source"]["rejected"] == 2
    assert report["experiments"] == []
    assert {row["reason"] for row in report["rejections"]} == {"parse_error", "range_error"}
    assert_report_matches_expected(report, expected)


def test_status_precedence_and_calibration_summary(tmp_path: Path) -> None:
    """Escaped takes precedence over noisy, and calibration aggregates use rounded escape rates."""
    spec_dir = tmp_path / "status-cards"
    calibration = tmp_path / "profiles.json"
    output = tmp_path / "status-report.json"
    suffix = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8]
    escaped_profile = "p_" + suffix + "_a"
    noisy_profile = "p_" + suffix + "_b"
    calm_profile = "p_" + suffix + "_c"
    escaped_name = "case_" + suffix + "_a"
    noisy_name = "case_" + suffix + "_b"
    calm_name = "case_" + suffix + "_c"
    write_json(calibration, {
        "profiles": {
            escaped_profile: {"driftScale": 1, "volatilityScale": 0.5, "driftBias": 0, "confidenceK": 1.96, "ciLimit": -0.5, "escapeThreshold": -0.01, "dependencyAttenuation": 0},
            noisy_profile: {"driftScale": 1, "volatilityScale": 1.0, "driftBias": 0, "confidenceK": 1.96, "ciLimit": -0.01, "escapeThreshold": 2.0, "dependencyAttenuation": 0},
            calm_profile: {"driftScale": 0.5, "volatilityScale": 0.1, "driftBias": 0, "confidenceK": 1.0, "ciLimit": 100.0, "escapeThreshold": 2.0, "dependencyAttenuation": 0},
        }
    })
    base_spec = {
        "apiVersion": "diffusion.ops/v1",
        "kind": "DiffusionExperiment",
        "container": {"image": "registry.status/sample:1"},
        "spec": {
            "seed": 700,
            "walkers": 6,
            "steps": 3,
            "drift": 0.01,
            "volatility": 0.12,
            "calibrationRef": escaped_profile,
            "dimensions": [{"name": "x", "weight": 1.0, "lower": -5.0, "upper": 5.0}],
        },
    }
    for revision, (name, profile, seed) in enumerate([(escaped_name, escaped_profile, 700), (noisy_name, noisy_profile, 701), (calm_name, calm_profile, 702)]):
        card = json.loads(json.dumps(base_spec))
        card["metadata"] = {"name": name, "revision": revision}
        card["spec"]["calibrationRef"] = profile
        card["spec"]["seed"] = seed
        write_json(spec_dir / f"{name}.json", card)
    expected = expected_report(spec_dir, calibration)
    report = run_report(spec_dir=spec_dir, calibration=calibration, output=output)
    assert_report_matches_expected(report, expected)
    statuses = sorted(exp["status"] for exp in report["experiments"])
    assert statuses == ["converged", "escaped", "noisy"]
    assert report["summary"]["status_counts"] == {"converged": 1, "noisy": 1, "escaped": 1}


def test_reducer_selects_highest_risk_before_revision(tmp_path: Path) -> None:
    """Cohort reduction must use simulated risk before revision and emit superseded rows."""
    spec_dir = tmp_path / "cohort-cards"
    calibration = tmp_path / "cohort-profiles.json"
    output = tmp_path / "cohort-report.json"
    write_json(calibration, {
        "profiles": {
            "cohort-profile": {
                "driftScale": 1,
                "volatilityScale": 0.25,
                "driftBias": 0,
                "confidenceK": 1.96,
                "ciLimit": 0.25,
                "escapeThreshold": 0.2,
                "dependencyAttenuation": 0.4,
                "dimensionAdjustments": {"*": {"weightScale": 1.5}, "x": {"weightBias": -0.2, "lowerShift": 0.05, "upperShift": -0.05}},
            }
        }
    })
    shared_container = {
        "image": "registry.reduce/team/app:old",
        "digest": "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    }
    write_json(spec_dir / "high-risk-low-revision.json", {
        "apiVersion": "diffusion.ops/v1",
        "kind": "DiffusionExperiment",
        "metadata": {"name": "high-risk-low-revision", "revision": 1},
        "container": shared_container,
        "spec": {
            "seed": 777,
            "walkers": 9,
            "steps": 7,
            "drift": 0.2,
            "volatility": 0.05,
            "calibrationRef": "cohort-profile",
            "dimensions": [{"name": "x", "weight": 1.0, "lower": -0.35, "upper": 0.35}],
        },
    })
    write_json(spec_dir / "low-risk-high-revision.json", {
        "apiVersion": "diffusion.ops/v1",
        "kind": "DiffusionExperiment",
        "metadata": {"name": "low-risk-high-revision", "revision": 50},
        "container": shared_container,
        "spec": {
            "seed": 778,
            "walkers": 9,
            "steps": 2,
            "drift": 0.0,
            "volatility": 0.0,
            "calibrationRef": "cohort-profile",
            "dimensions": [{"name": "x", "weight": 1.0, "lower": -10.0, "upper": 10.0}],
        },
    })
    expected = expected_report(spec_dir, calibration)
    report = run_report(spec_dir=spec_dir, calibration=calibration, output=output)
    assert_report_matches_expected(report, expected)
    assert [exp["id"] for exp in report["experiments"]] == ["high-risk-low-revision"]
    assert report["experiments"][0]["revision"] == 1
    assert report["experiments"][0]["risk_score"] > 100
    assert report["experiments"][0]["dimensions"][0]["weight"] == 1.3
    assert [(row["file"], row["reason"]) for row in report["rejections"]] == [("low-risk-high-revision.json", "superseded")]



def test_profile_inheritance_and_retention_policy_are_coupled(tmp_path: Path) -> None:
    """Resolved inherited profiles must drive simulation, retention rejection, and digest."""
    spec_dir = tmp_path / "inherit-retention-cards"
    calibration = tmp_path / "inheritance-profiles.json"
    output = tmp_path / "inheritance-report.json"
    write_json(calibration, {
        "profiles": {
            "parent": {
                "driftScale": 0.6,
                "volatilityScale": 0.5,
                "driftBias": 0.001,
                "confidenceK": 1.5,
                "ciLimit": 0.4,
                "escapeThreshold": 0.6,
                "dependencyAttenuation": 0.25,
                "dimensionAdjustments": {"*": {"weightScale": 1.2, "lowerShift": -0.1}, "hot": {"upperShift": 0.1}},
                "retention": {"maxExperiments": 1, "riskWindow": 0},
            },
            "child": {
                "inherits": "parent",
                "driftScale": 1.4,
                "volatilityScale": 1.1,
                "escapeThreshold": 0.25,
                "dimensionAdjustments": {"hot": {"weightBias": 0.25}},
            },
            "bad-parent": {"inherits": "missing-parent", "driftScale": 1},
        }
    })
    for name, seed, image, drift, volatility, steps in [
        ("hot-risk-kept", 811, "registry.inherit/app/hot:1", 0.16, 0.03, 5),
        ("cold-risk-dropped", 812, "registry.inherit/app/cold:1", 0.0, 0.0, 2),
    ]:
        write_json(spec_dir / f"{name}.json", {
            "apiVersion": "diffusion.ops/v1",
            "kind": "DiffusionExperiment",
            "metadata": {"name": name, "revision": 1},
            "container": {"image": image},
            "spec": {
                "seed": seed,
                "walkers": 8,
                "steps": steps,
                "drift": drift,
                "volatility": volatility,
                "calibrationRef": "child",
                "dimensions": [{"name": "hot", "weight": 1.0, "lower": -0.45, "upper": 0.45}],
            },
        })
    write_json(spec_dir / "bad-inherited-profile.json", {
        "apiVersion": "diffusion.ops/v1",
        "kind": "DiffusionExperiment",
        "metadata": {"name": "bad-inherited-profile"},
        "container": {"image": "registry.inherit/bad:1"},
        "spec": {
            "seed": 900,
            "walkers": 3,
            "steps": 2,
            "drift": 0.01,
            "volatility": 0.1,
            "calibrationRef": "bad-parent",
            "dimensions": [{"name": "hot", "weight": 1, "lower": -1, "upper": 1}],
        },
    })
    expected = expected_report(spec_dir, calibration)
    report = run_report(spec_dir=spec_dir, calibration=calibration, output=output)
    assert_report_matches_expected(report, expected)
    assert [row["id"] for row in report["experiments"]] == ["hot-risk-kept"]
    assert [(row["file"], row["reason"]) for row in report["rejections"]] == [
        ("bad-inherited-profile.json", "calibration_missing"),
        ("cold-risk-dropped.json", "retention_excluded"),
    ]
    hot_dimension = report["experiments"][0]["dimensions"][0]
    assert hot_dimension["weight"] == 1.45


def test_dependency_graph_drives_cohort_risk_and_rejections(tmp_path: Path) -> None:
    """Dependency propagation must affect cohort winners and reject missing/cyclic graphs."""
    spec_dir = tmp_path / "dependency-cards"
    calibration = tmp_path / "dependency-profiles.json"
    output = tmp_path / "dependency-report.json"
    write_json(calibration, {
        "profiles": {
            "link-profile": {
                "driftScale": 1,
                "volatilityScale": 1,
                "driftBias": 0,
                "confidenceK": 1.96,
                "ciLimit": 0.05,
                "escapeThreshold": 2,
                "dependencyAttenuation": 1.0,
            },
            "boost-profile": {
                "driftScale": 1,
                "volatilityScale": 0.1,
                "driftBias": 0,
                "confidenceK": 1.96,
                "ciLimit": 100,
                "escapeThreshold": -0.01,
                "dependencyAttenuation": 0.0,
            },
        }
    })

    def card(name: str, image: str, seed: int, drift: float, volatility: float, profile: str, depends: list[str] | None = None, revision: int = 0) -> dict[str, Any]:
        spec: dict[str, Any] = {
            "seed": seed,
            "walkers": 8,
            "steps": 4,
            "drift": drift,
            "volatility": volatility,
            "calibrationRef": profile,
            "dimensions": [{"name": "x", "weight": 1.0, "lower": -1.0, "upper": 1.0}],
        }
        if depends is not None:
            spec["dependsOn"] = depends
        return {
            "apiVersion": "diffusion.ops/v1",
            "kind": "DiffusionExperiment",
            "metadata": {"name": name, "revision": revision},
            "container": {"image": image},
            "spec": spec,
        }

    shared_image = "registry.dependencies/app:1"
    write_json(spec_dir / "00-boost.json", card("boost-node", "registry.dependencies/boost:1", 991, 0.35, 0.0, "boost-profile"))
    write_json(spec_dir / "10-dependent-low-local.json", card("dependent-low-local", shared_image, 992, 0.0, 0.0, "link-profile", ["boost-node"], revision=1))
    write_json(spec_dir / "20-independent-higher-local.json", card("independent-higher-local", shared_image, 993, 0.0, 0.3, "link-profile", revision=99))
    write_json(spec_dir / "30-missing.json", card("missing-edge", "registry.dependencies/missing:1", 994, 0.0, 0.0, "link-profile", ["absent-node"]))
    write_json(spec_dir / "40-cycle-a.json", card("cycle-a", "registry.dependencies/cycle-a:1", 995, 0.0, 0.0, "link-profile", ["cycle-b"]))
    write_json(spec_dir / "41-cycle-b.json", card("cycle-b", "registry.dependencies/cycle-b:1", 996, 0.0, 0.0, "link-profile", ["cycle-a"]))

    expected = expected_report(spec_dir, calibration)
    report = run_report(spec_dir=spec_dir, calibration=calibration, output=output)
    assert_report_matches_expected(report, expected)
    by_id = {row["id"]: row for row in report["experiments"]}
    assert set(by_id) == {"boost-node", "dependent-low-local"}
    assert by_id["dependent-low-local"]["dependencies"] == ["boost-node"]
    assert by_id["dependent-low-local"]["dependency_risk"] > by_id["dependent-low-local"]["risk_score"]
    assert [(row["file"], row["reason"]) for row in report["rejections"]] == [
        ("20-independent-higher-local.json", "superseded"),
        ("30-missing.json", "dependency_missing"),
        ("40-cycle-a.json", "dependency_cycle"),
        ("41-cycle-b.json", "dependency_cycle"),
    ]
