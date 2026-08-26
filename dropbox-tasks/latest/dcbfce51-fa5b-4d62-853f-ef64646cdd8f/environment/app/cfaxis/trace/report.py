"""Trace manifest execution and reporting."""

from __future__ import annotations

import hashlib
import json
import struct
import tomllib
from dataclasses import dataclass
from pathlib import Path

from cfaxis.append import append_datasets
from cfaxis.error import ValidationError
from cfaxis.formats import read_dataset, write_dataset
from cfaxis.formats.io import FormatArg, FreqArg
from cfaxis.provenance import operation_hash
from cfaxis.resample import resample_dataset
from cfaxis.time import normalize_bounds_to_1970_days


@dataclass
class TraceStep:
    op: str
    input: str | None = None
    output: str | None = None
    base: str | None = None
    append: str | None = None
    freq: str | None = None


@dataclass
class ScenarioSpec:
    name: str
    steps: list[TraceStep]
    seed: str | None = None


@dataclass
class TraceManifest:
    schema_version: int
    scenarios: list[ScenarioSpec]


def run_trace(manifest_path: Path, out_path: Path) -> None:
    text = manifest_path.read_text()
    raw = tomllib.loads(text)
    if raw["schema_version"] != 3:
        raise ValidationError(
            f"manifest schema_version must be 3, got {raw['schema_version']}"
        )

    scenarios: list[ScenarioSpec] = []
    for s in raw["scenarios"]:
        steps = [
            TraceStep(
                op=st["op"],
                input=st.get("input"),
                output=st.get("output"),
                base=st.get("base"),
                append=st.get("append"),
                freq=st.get("freq"),
            )
            for st in s["steps"]
        ]
        scenarios.append(
            ScenarioSpec(name=s["name"], steps=steps, seed=s.get("seed"))
        )
    manifest = TraceManifest(schema_version=raw["schema_version"], scenarios=scenarios)

    work = Path("/tmp/cfaxis-trace")
    work.mkdir(parents=True, exist_ok=True)

    results = [run_scenario(scenario, work) for scenario in manifest.scenarios]

    report = {
        "schema_version": 3,
        "generated_at": "1970-01-01T00:00:00Z",
        "scenarios": results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))


def run_scenario(spec: ScenarioSpec, work: Path) -> dict:
    current: Path | None = None
    input_digest = ""
    paths_for_hash: list[str] = []

    for step in spec.steps:
        if step.op == "convert":
            if step.input is not None:
                work_rel = work / step.input
                inp = work_rel if work_rel.exists() else resolve_path(step.input)
            else:
                if current is None:
                    raise ValidationError("convert missing input")
                inp = current
            out = work / step.output
            if not input_digest:
                input_digest = file_digest(inp)
            ds = read_dataset(inp, FormatArg.AUTO)
            write_dataset(out, ds, FormatArg.AUTO)
            current = out
            paths_for_hash.append(str(inp))
        elif step.op == "append":
            base = resolve_path(step.base)
            app = resolve_path(step.append)
            out = work / step.output
            base_ds = read_dataset(base, FormatArg.AUTO)
            app_ds = read_dataset(app, FormatArg.AUTO)
            append_datasets(base_ds, app_ds, out)
            current = out
        elif step.op == "resample":
            if current is not None:
                inp = current
            else:
                inp = resolve_path(step.input)
            out = work / step.output
            freq = parse_freq(step.freq or "mon")
            cache = Path("/var/lib/climconvert/cache")
            resample_dataset(inp, freq, out, cache, True)
            current = out
        else:
            raise ValidationError(f"unknown trace op: {step.op}")

    if current is None:
        raise ValidationError("no output from scenario")
    ds = read_dataset(current, FormatArg.AUTO)

    ok, mismatch, canonical_sample, append_order_ok = evaluate_scenario(spec, ds)

    bounds_hash = None
    if ds.bounds_axis is not None:
        hasher = hashlib.sha256()
        for pair in ds.bounds_axis.encoded_pairs():
            hasher.update(struct.pack("<d", pair[0]))
            hasher.update(struct.pack("<d", pair[1]))
        bounds_hash = hasher.hexdigest()

    return {
        "name": spec.name,
        "ok": ok,
        "input_digest": input_digest,
        "instant_mismatch_count": mismatch,
        "bounds_hash": bounds_hash,
        "append_order_ok": append_order_ok,
        "canonical_instant_sample": canonical_sample,
        "operation_hash": operation_hash(spec.name, paths_for_hash),
        "notes": "",
    }


def evaluate_scenario(
    spec: ScenarioSpec, ds
) -> tuple[bool, int, list[int] | None, bool | None]:
    name = spec.name
    if name == "gregorian_roundtrip":
        mismatches = count_instant_mismatches(ds)
        sample = [round(v) for v in ds.time_axis.encoded_values()[:3]]
        return mismatches == 0, mismatches, sample, None
    if name in ("proleptic_roundtrip", "360day_roundtrip", "double_roundtrip_chain"):
        mismatches = count_instant_mismatches(ds)
        return mismatches == 0, mismatches, None, None
    if name == "bounds_roundtrip":
        mismatches = count_bounds_mismatches(ds)
        return mismatches == 0, mismatches, None, None
    if name == "mixed_units_append":
        order_ok = check_append_order(ds)
        return order_ok, 0, None, order_ok
    if name == "resample_monthly":
        mismatches = count_resample_mismatches(ds)
        return mismatches == 0, mismatches, None, None
    return False, 1, None, None


def count_instant_mismatches(ds) -> int:
    cal = ds.time_axis.calendar
    units = ds.time_axis.units
    mismatches = 0
    for inst in ds.time_axis.instants:
        y, m, d = cal.days_from_origin_to_ymd(
            units.origin_year,
            units.origin_month,
            units.origin_day,
            inst.encoded_value,
        )
        back = cal.ymd_to_encoded_days(units, y, m, d)
        y2, m2, d2 = cal.days_from_origin_to_ymd(
            units.origin_year,
            units.origin_month,
            units.origin_day,
            back,
        )
        if (y, m, d) != (y2, m2, d2):
            mismatches += 1
    return mismatches


def count_bounds_mismatches(ds) -> int:
    if ds.bounds_axis is None:
        return 0
    b = ds.bounds_axis
    mismatches = 0
    for pair in b.encoded_pairs():
        lo, hi = normalize_bounds_to_1970_days(b.calendar, b.units, pair[0], pair[1])
        if lo > hi:
            mismatches += 1
    return mismatches


def check_append_order(ds) -> bool:
    cal = ds.time_axis.calendar
    units = ds.time_axis.units
    keys = [i.sort_key(cal, units) for i in ds.time_axis.instants]
    return all(keys[i] <= keys[i + 1] for i in range(len(keys) - 1))


def count_resample_mismatches(ds) -> int:
    if not ds.time_axis.instants:
        return 1
    cal = ds.time_axis.calendar
    units = ds.time_axis.units
    prev = -(2**63)
    for inst in ds.time_axis.instants:
        key = inst.sort_key(cal, units)
        if key < prev:
            return 1
        prev = key
    return 0


def resolve_path(p: str) -> Path:
    pb = Path(p)
    if pb.is_absolute():
        return pb
    return Path("/app") / p


def file_digest(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        data = b""
    return hashlib.sha256(data).hexdigest()


def parse_freq(s: str) -> FreqArg:
    if s == "sea":
        return FreqArg.SEA
    if s == "ann":
        return FreqArg.ANN
    return FreqArg.MON
