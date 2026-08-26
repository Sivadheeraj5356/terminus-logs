"""Independent oracle for piezoelectric resonance audit (schema v4 batch)."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import subprocess
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest

from rebuild_helper import rebuild

ROOT = Path("/app")
APP = ROOT / "environment" if (ROOT / "environment").exists() else Path(__file__).resolve().parents[1] / "environment"
FIXTURES = APP / "fixtures"
PROFILES = FIXTURES / "profiles"
HIDDEN = Path(__file__).resolve().parent / "testdata" / "chips"
GOLDEN = Path(__file__).resolve().parent / "testdata" / "golden"
OUT_DIR = ROOT / "output"
MANIFEST = OUT_DIR / "resonance_manifest.json"
CACHE = OUT_DIR / "resonance_row_cache.json"
DEFAULT_AS_OF = "2099-12-31"
SCHEMA_VERSION = 4


def _round4(value: float) -> float:
    return float(
        Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    )


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _days_in_month(year: int, month: int) -> int:
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    if month == 2:
        return 29 if _is_leap(year) else 28
    return 30


def _add_days(date: str, days: int) -> str:
    year, month, day = (int(part) for part in date.split("-"))
    remaining = days
    while remaining > 0:
        dim = _days_in_month(year, month)
        day_left = dim - day
        if remaining <= day_left:
            day += remaining
            remaining = 0
        else:
            remaining -= day_left + 1
            day = 1
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _load_catalog() -> list[dict]:
    revisions: list[dict] = []
    for path in sorted(PROFILES.glob("*.prof")):
        profile_id = ""
        effective_date = ""
        inherits = ""
        alpha = 0.0
        nominal_hz_override = 0.0
        deprecation_window_days = 0
        for raw in path.read_text().splitlines():
            line = raw.split("#", 1)[0].strip()
            if line.startswith("profile_id="):
                profile_id = line.split("=", 1)[1].strip()
            elif line.startswith("effective_date="):
                effective_date = line.split("=", 1)[1].strip()
            elif line.startswith("inherits="):
                inherits = line.split("=", 1)[1].strip()
            elif line.startswith("alpha="):
                token = line.split("=", 1)[1].strip()
                if token:
                    alpha = float(token)
            elif line.startswith("nominal_hz_override="):
                token = line.split("=", 1)[1].strip()
                if token:
                    nominal_hz_override = float(token)
            elif line.startswith("deprecation_window_days="):
                deprecation_window_days = int(line.split("=", 1)[1].strip())
        revisions.append(
            {
                "profile_id": profile_id,
                "effective_date": effective_date,
                "inherits": inherits,
                "alpha": alpha,
                "nominal_hz_override": nominal_hz_override,
                "deprecation_window_days": deprecation_window_days,
            }
        )
    return revisions


def _is_deprecated(revision: dict, catalog: list[dict], as_of: str) -> bool:
    for newer in catalog:
        if newer["profile_id"] != revision["profile_id"]:
            continue
        if newer["effective_date"] <= revision["effective_date"]:
            continue
        if newer["effective_date"] > as_of:
            continue
        window = newer["deprecation_window_days"]
        if window == 0:
            return True
        deprecate_after = _add_days(newer["effective_date"], window)
        if as_of > deprecate_after:
            return True
    return False


def _select_revision(catalog: list[dict], profile_id: str, as_of: str) -> dict:
    best: dict | None = None
    for revision in catalog:
        if revision["profile_id"] != profile_id:
            continue
        if revision["effective_date"] > as_of:
            continue
        if _is_deprecated(revision, catalog, as_of):
            continue
        if best is None or revision["effective_date"] > best["effective_date"]:
            best = revision
    if best is None:
        raise ValueError(f"no profile {profile_id} for as_of {as_of}")
    return best


def _resolve_profile(
    catalog: list[dict],
    revision: dict,
    as_of: str,
    seen: list[str] | None = None,
) -> dict:
    seen = list(seen or [])
    if revision["profile_id"] in seen:
        raise ValueError(f"inheritance cycle at {revision['profile_id']}")
    seen.append(revision["profile_id"])

    resolved_alpha = revision["alpha"]
    resolved_nominal = revision["nominal_hz_override"]
    parent_effective_date = ""

    if revision["inherits"]:
        parent = _select_revision(catalog, revision["inherits"], as_of)
        parent_effective_date = parent["effective_date"]
        parent_resolved = _resolve_profile(catalog, parent, as_of, seen)
        if resolved_alpha <= 0.0:
            resolved_alpha = parent_resolved["resolved_alpha"]
        if resolved_nominal <= 0.0:
            resolved_nominal = parent_resolved["resolved_nominal_override"]

    if resolved_alpha <= 0.0:
        raise ValueError(f"unresolved alpha for profile {revision['profile_id']}")

    return {
        "revision": revision,
        "parent_effective_date": parent_effective_date,
        "resolved_alpha": resolved_alpha,
        "resolved_nominal_override": resolved_nominal,
    }


def _collect_lineage(
    catalog: list[dict], resolved: dict, as_of: str
) -> list[dict]:
    chain = [resolved["revision"].copy()]
    if resolved["revision"]["inherits"]:
        parent = _select_revision(catalog, resolved["revision"]["inherits"], as_of)
        parent_resolved = _resolve_profile(catalog, parent, as_of, [])
        chain.extend(_collect_lineage(catalog, parent_resolved, as_of))
    chain.sort(key=lambda rev: (rev["profile_id"], rev["effective_date"]))
    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for rev in chain:
        key = (rev["profile_id"], rev["effective_date"])
        if key not in seen:
            seen.add(key)
            deduped.append(rev)
    return deduped


def _parse_chip(path: Path) -> dict:
    family_id = ""
    chip_id = ""
    alias = ""
    profile_id = ""
    nominal_hz = 0.0
    readings: list[dict] = []
    segment_overrides: dict[str, dict[str, float]] = {}
    in_readings = False
    segment_id = "default"

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        comment_at = line.find("#")
        line = line[:comment_at].strip() if comment_at >= 0 else line
        if not line:
            continue
        if line.startswith("family_id="):
            family_id = line.split("=", 1)[1].strip()
            in_readings = False
        elif line.startswith("chip_id="):
            chip_id = line.split("=", 1)[1].strip()
            in_readings = False
        elif line.startswith("alias="):
            alias = line.split("=", 1)[1].strip()
            in_readings = False
        elif line.startswith("profile_id="):
            profile_id = line.split("=", 1)[1].strip()
            in_readings = False
        elif line.startswith("nominal_hz="):
            nominal_hz = float(line.split("=", 1)[1])
            in_readings = False
        elif line == "readings:":
            in_readings = True
            segment_id = "default"
        elif line.startswith("segment:"):
            segment_id = line.split(":", 1)[1].strip()
            segment_overrides.setdefault(
                segment_id, {"alpha_override": 0.0, "nominal_hz_override": 0.0}
            )
        elif line.startswith("alpha_override="):
            segment_overrides.setdefault(
                segment_id, {"alpha_override": 0.0, "nominal_hz_override": 0.0}
            )["alpha_override"] = float(line.split("=", 1)[1])
        elif line.startswith("nominal_hz_override="):
            segment_overrides.setdefault(
                segment_id, {"alpha_override": 0.0, "nominal_hz_override": 0.0}
            )["nominal_hz_override"] = float(line.split("=", 1)[1])
        elif in_readings:
            line_index, temp_c, freq_hz = line.split()
            readings.append(
                {
                    "line_index": int(line_index),
                    "segment_id": segment_id,
                    "temp_c": float(temp_c),
                    "freq_hz": float(freq_hz),
                }
            )

    if not family_id or not chip_id or not profile_id or nominal_hz <= 0 or not readings:
        raise ValueError(f"{path}: invalid chip file")
    return {
        "family_id": family_id,
        "chip_id": chip_id,
        "alias": alias,
        "profile_id": profile_id,
        "nominal_hz": nominal_hz,
        "readings": readings,
        "segment_overrides": segment_overrides,
    }


def _segment_ids(profile: dict) -> list[str]:
    ids: list[str] = []
    for row in profile["readings"]:
        sid = row["segment_id"]
        if sid not in ids:
            ids.append(sid)
    return ids


def _effective_alpha(profile: dict, resolved: dict, segment_id: str) -> float:
    seg = profile["segment_overrides"].get(segment_id)
    if seg and seg["alpha_override"] > 0.0:
        return seg["alpha_override"]
    return resolved["resolved_alpha"]


def _effective_nominal_for_reading(
    profile: dict, resolved: dict, segment_id: str
) -> float:
    seg = profile["segment_overrides"].get(segment_id)
    if seg and seg["nominal_hz_override"] > 0.0:
        return seg["nominal_hz_override"]
    if resolved["resolved_nominal_override"] > 0.0:
        return resolved["resolved_nominal_override"]
    return profile["nominal_hz"]


def _effective_nominal_header(profile: dict, resolved: dict) -> float:
    if resolved["resolved_nominal_override"] > 0.0:
        return resolved["resolved_nominal_override"]
    return profile["nominal_hz"]


def _freq_at_25(freq_hz: float, temp_c: float, alpha: float) -> float:
    return _round4(freq_hz / (1.0 + alpha * (temp_c - 25.0)))


def _ppm_pull(freq_25_hz: float, nominal_hz: float) -> float:
    return _round4((freq_25_hz - nominal_hz) / nominal_hz * 1_000_000.0)


def _weight(temp_c: float) -> float:
    return 1.0 if temp_c == 25.0 else 1.0 / abs(temp_c - 25.0)


def _weighted_mean_ppm(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    weighted = sum(row["ppm_pull"] * _weight(row["temp_c"]) for row in rows)
    total = sum(_weight(row["temp_c"]) for row in rows)
    return _round4(weighted / total)


def _sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (row["temp_c"], row["line_index"]))


def _rows_from_profile(profile: dict, resolved: dict) -> list[dict]:
    rows = []
    for reading in profile["readings"]:
        alpha = _effective_alpha(profile, resolved, reading["segment_id"])
        nominal = _effective_nominal_for_reading(
            profile, resolved, reading["segment_id"]
        )
        freq_25 = _freq_at_25(reading["freq_hz"], reading["temp_c"], alpha)
        rows.append(
            {
                "line_index": reading["line_index"],
                "segment_id": reading["segment_id"],
                "temp_c": reading["temp_c"],
                "freq_hz": reading["freq_hz"],
                "freq_25_hz": freq_25,
                "ppm_pull": _ppm_pull(freq_25, nominal),
            }
        )
    return _sort_rows(rows)


def _source_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint_inputs(paths: list[Path], as_of: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(as_of.encode())
    hasher.update(b"\n")
    for path in paths:
        hasher.update(str(path).encode())
        hasher.update(b"\n")
        hasher.update(path.read_bytes())
        hasher.update(b"\n")
    return "sha256:" + hasher.hexdigest()


def _profile_hash_float(value: float) -> str:
    if value == 0.0:
        return "0"
    rendered = format(Decimal(str(value)), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _digest_float_token(value: float) -> str:
    if value == 0.0:
        return "0"
    scaled = int(round(value * 10000.0))
    negative = scaled < 0
    abs_scaled = abs(scaled)
    whole = abs_scaled // 10000
    frac = abs_scaled % 10000
    if frac == 0:
        return f"{'-' if negative else ''}{whole}"
    frac_digits = f"{frac:04}".rstrip("0")
    return f"{'-' if negative else ''}{whole}.{frac_digits}"


def _lineage_json_float(value: float) -> str:
    if value == 0.0:
        return "0.0"
    token = _profile_hash_float(value)
    return token if "." in token else f"{token}.0"


def _row_json_float(value: float) -> str:
    if value == 0.0:
        return "0.0"
    token = _digest_float_token(value)
    return token if "." in token else f"{token}.0"


def _profile_graph_hash_body(
    revisions: list[dict], segment_overrides: list[dict]
) -> str:
    unique_revs = sorted(
        {(rev["profile_id"], rev["effective_date"]): rev for rev in revisions}.values(),
        key=lambda rev: (rev["profile_id"], rev["effective_date"]),
    )
    segs = sorted(
        segment_overrides,
        key=lambda seg: (seg["family_id"], seg["chip_id"], seg["segment_id"]),
    )
    lines: list[str] = []
    for revision in unique_revs:
        override_token = (
            _profile_hash_float(revision["nominal_hz_override"])
            if revision["nominal_hz_override"] > 0.0
            else "0"
        )
        lines.append(
            f"{revision['profile_id']}|{revision['effective_date']}|"
            f"{_profile_hash_float(revision['alpha'])}|{override_token}|"
            f"{revision['inherits']}|{revision['deprecation_window_days']}"
        )
    for seg in segs:
        alpha = (
            _profile_hash_float(seg["alpha_override"])
            if seg["alpha_override"] > 0.0
            else "0"
        )
        nominal = (
            _profile_hash_float(seg["nominal_hz_override"])
            if seg["nominal_hz_override"] > 0.0
            else "0"
        )
        lines.append(
            f"{seg['family_id']}|{seg['chip_id']}|{seg['segment_id']}|{alpha}|{nominal}"
        )
    return "\n".join(lines) + ("\n" if lines else "")


def _profile_graph_hash(
    revisions: list[dict], segment_overrides: list[dict]
) -> str:
    body = _profile_graph_hash_body(revisions, segment_overrides)
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def _merge_batch(paths: list[Path], as_of: str) -> dict:
    catalog = _load_catalog()
    loaded: list[dict] = []
    for path in paths:
        profile = _parse_chip(path)
        revision = _select_revision(catalog, profile["profile_id"], as_of)
        resolved = _resolve_profile(catalog, revision, as_of)
        lineage = _collect_lineage(catalog, resolved, as_of)
        loaded.append(
            {
                "path": str(path),
                "profile": profile,
                "resolved": resolved,
                "lineage": lineage,
            }
        )

    alias_first_chip: dict[str, str] = {}
    alias_rewrite: dict[str, str] = {}
    for item in loaded:
        alias = item["profile"]["alias"]
        if not alias:
            continue
        chip_id = item["profile"]["chip_id"]
        if alias in alias_first_chip:
            if alias_first_chip[alias] != chip_id:
                alias_rewrite[alias_first_chip[alias]] = f"{alias}@{alias_first_chip[alias]}"
        else:
            alias_first_chip[alias] = chip_id

    by_family: dict[str, list[dict]] = {}
    for item in loaded:
        by_family.setdefault(item["profile"]["family_id"], []).append(item)

    all_revisions: list[dict] = []
    all_segment_overrides: list[dict] = []
    families: dict[str, dict] = {}

    for family_id, family_items in by_family.items():
        by_key: dict[tuple[str, str], dict] = {}
        provenance: list[dict] = []
        last_item: dict | None = None
        lineage_revisions: list[dict] = []

        for item in family_items:
            for rev in item["lineage"]:
                key = (rev["profile_id"], rev["effective_date"])
                if not any(
                    r["profile_id"] == key[0] and r["effective_date"] == key[1]
                    for r in all_revisions
                ):
                    all_revisions.append(rev.copy())
            lineage_revisions = [rev.copy() for rev in item["lineage"]]

            profile = item["profile"]
            for seg_id, seg_ov in profile["segment_overrides"].items():
                if seg_ov["alpha_override"] > 0.0 or seg_ov["nominal_hz_override"] > 0.0:
                    entry = {
                        "family_id": profile["family_id"],
                        "chip_id": profile["chip_id"],
                        "segment_id": seg_id,
                        "alpha_override": seg_ov["alpha_override"],
                        "nominal_hz_override": seg_ov["nominal_hz_override"],
                    }
                    if not any(
                        s["family_id"] == entry["family_id"]
                        and s["chip_id"] == entry["chip_id"]
                        and s["segment_id"] == entry["segment_id"]
                        for s in all_segment_overrides
                    ):
                        all_segment_overrides.append(entry)

            alias = alias_rewrite.get(
                item["profile"]["chip_id"], item["profile"]["alias"]
            )
            provenance.append(
                {
                    "path": item["path"],
                    "family_id": item["profile"]["family_id"],
                    "chip_id": item["profile"]["chip_id"],
                    "alias": alias,
                    "profile_id": item["profile"]["profile_id"],
                    "profile_effective_date": item["resolved"]["revision"]["effective_date"],
                    "profile_parent_effective_date": item["resolved"]["parent_effective_date"],
                    "segment_ids": _segment_ids(item["profile"]),
                    "reading_count": len(item["profile"]["readings"]),
                    "source_digest": _source_digest(Path(item["path"])),
                }
            )

            merge_key = (item["profile"]["chip_id"], item["profile"]["profile_id"])
            by_key[merge_key] = item["profile"]
            last_item = item

        assert last_item is not None
        active_key = (
            last_item["profile"]["chip_id"],
            last_item["profile"]["profile_id"],
        )
        active = by_key[active_key]
        families[family_id] = {
            "profile": active,
            "provenance": provenance,
            "resolved": last_item["resolved"],
            "lineage_revisions": lineage_revisions,
        }

    return {
        "families": families,
        "all_revisions": all_revisions,
        "all_segment_overrides": all_segment_overrides,
    }


def _json_float(value: float) -> str:
    return _lineage_json_float(value)


def _json_string_array(values: list[str]) -> str:
    return "[" + ",".join(json.dumps(v) for v in values) + "]"


def _resonance_digest_body(
    family_id: str,
    chip_id: str,
    profile_id: str,
    profile_graph_hash: str,
    as_of_date: str,
    input_fingerprint: str,
    branch_generation: int,
    lineage: list[dict],
    provenance: list[dict],
    rows: list[dict],
) -> str:
    body = "{"
    body += '"family_id":' + json.dumps(family_id)
    body += ',"chip_id":' + json.dumps(chip_id)
    body += ',"profile_id":' + json.dumps(profile_id)
    body += ',"profile_graph_hash":' + json.dumps(profile_graph_hash)
    body += ',"as_of_date":' + json.dumps(as_of_date)
    body += ',"input_fingerprint":' + json.dumps(input_fingerprint)
    body += f',"branch_generation":{branch_generation}'
    body += f',"reading_count":{len(rows)}'
    body += ',"profile_lineage":['
    for index, entry in enumerate(lineage):
        if index:
            body += ","
        nom = entry["nominal_hz_override"] if entry["nominal_hz_override"] > 0.0 else 0.0
        body += "{"
        body += '"profile_id":' + json.dumps(entry["profile_id"])
        body += ',"effective_date":' + json.dumps(entry["effective_date"])
        body += ',"inherits":' + json.dumps(entry["inherits"])
        body += ',"alpha":' + _lineage_json_float(entry["alpha"])
        body += ',"nominal_hz_override":' + _lineage_json_float(nom)
        body += f',"deprecation_window_days":{entry["deprecation_window_days"]}'
        body += "}"
    body += '],"provenance":['
    for index, entry in enumerate(provenance):
        if index:
            body += ","
        body += "{"
        body += '"path":' + json.dumps(entry["path"])
        body += ',"family_id":' + json.dumps(entry["family_id"])
        body += ',"chip_id":' + json.dumps(entry["chip_id"])
        body += ',"alias":' + json.dumps(entry["alias"])
        body += ',"profile_id":' + json.dumps(entry["profile_id"])
        body += ',"profile_effective_date":' + json.dumps(entry["profile_effective_date"])
        body += ',"profile_parent_effective_date":' + json.dumps(
            entry["profile_parent_effective_date"]
        )
        body += ',"segment_ids":' + _json_string_array(entry["segment_ids"])
        body += f',"reading_count":{int(entry["reading_count"])}'
        body += ',"source_digest":' + json.dumps(entry["source_digest"])
        body += "}"
    body += '],"rows":['
    for index, row in enumerate(rows):
        if index:
            body += ","
        body += "{"
        body += f'"line_index":{int(row["line_index"])}'
        body += ',"segment_id":' + json.dumps(row["segment_id"])
        body += ',"ppm_pull":' + _row_json_float(row["ppm_pull"])
        body += ',"temp_c":' + _row_json_float(row["temp_c"])
        body += "}"
    body += "]}"
    return body


def _resonance_digest(
    family_id: str,
    chip_id: str,
    profile_id: str,
    profile_graph_hash: str,
    as_of_date: str,
    input_fingerprint: str,
    branch_generation: int,
    lineage: list[dict],
    provenance: list[dict],
    rows: list[dict],
) -> str:
    body = _resonance_digest_body(
        family_id,
        chip_id,
        profile_id,
        profile_graph_hash,
        as_of_date,
        input_fingerprint,
        branch_generation,
        lineage,
        provenance,
        rows,
    )
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def _batch_digest_body(
    as_of_date: str,
    input_fingerprint: str,
    profile_graph_hash: str,
    batch_generation: int,
    family_digests: list[str],
) -> str:
    body = "{"
    body += f'"schema_version":{SCHEMA_VERSION}'
    body += ',"as_of_date":' + json.dumps(as_of_date)
    body += ',"input_fingerprint":' + json.dumps(input_fingerprint)
    body += ',"profile_graph_hash":' + json.dumps(profile_graph_hash)
    body += f',"batch_generation":{batch_generation}'
    body += f',"family_count":{len(family_digests)}'
    body += ',"family_digests":['
    for index, digest in enumerate(family_digests):
        if index:
            body += ","
        body += json.dumps(digest)
    body += "]}"
    return body


def _batch_digest(
    as_of_date: str,
    input_fingerprint: str,
    profile_graph_hash: str,
    batch_generation: int,
    family_digests: list[str],
) -> str:
    body = _batch_digest_body(
        as_of_date,
        input_fingerprint,
        profile_graph_hash,
        batch_generation,
        family_digests,
    )
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def _read_manifest() -> dict | None:
    if not MANIFEST.exists():
        return None
    try:
        return json.loads(MANIFEST.read_text())
    except json.JSONDecodeError:
        return None


def _resolve_batch_generation(
    input_fingerprint: str, profile_graph_hash: str, manifest: dict | None
) -> int:
    if not manifest:
        return 1
    if (
        manifest.get("last_input_fingerprint") == input_fingerprint
        and manifest.get("last_profile_graph_hash") == profile_graph_hash
    ):
        return max(int(manifest.get("batch_generation", 0)), 1)
    for entry in manifest.get("history", []):
        if (
            entry.get("input_fingerprint") == input_fingerprint
            and entry.get("profile_graph_hash") == profile_graph_hash
        ):
            return max(int(entry.get("batch_generation", 0)), 1)
    gens = [int(entry.get("batch_generation", 0)) for entry in manifest.get("history", [])]
    last = max(gens) if gens else 0
    return 1 if last == 0 else last + 1


def _resolve_branch_generation(
    family_id: str,
    input_fingerprint: str,
    profile_graph_hash: str,
    manifest: dict | None,
) -> int:
    if manifest:
        for branch in manifest.get("branches", []):
            if (
                branch.get("family_id") == family_id
                and branch.get("input_fingerprint") == input_fingerprint
                and branch.get("profile_graph_hash") == profile_graph_hash
            ):
                return max(int(branch.get("branch_generation", 0)), 1)
        max_branch = max(
            (int(branch.get("branch_generation", 0)) for branch in manifest.get("branches", [])),
            default=0,
        )
    else:
        max_branch = 0
    return 1 if max_branch == 0 else max_branch + 1


def _expected_report(
    paths: list[Path],
    as_of: str = DEFAULT_AS_OF,
    manifest_before: dict | None = None,
) -> dict:
    merged = _merge_batch(paths, as_of)
    input_fingerprint = _fingerprint_inputs(paths, as_of)
    profile_graph_hash = _profile_graph_hash(
        merged["all_revisions"], merged["all_segment_overrides"]
    )
    batch_generation = _resolve_batch_generation(
        input_fingerprint, profile_graph_hash, manifest_before
    )

    family_reports: list[dict] = []
    family_digests: list[str] = []

    for family_id in sorted(merged["families"]):
        family = merged["families"][family_id]
        profile = family["profile"]
        resolved = family["resolved"]
        branch_generation = _resolve_branch_generation(
            family_id, input_fingerprint, profile_graph_hash, manifest_before
        )
        rows = _rows_from_profile(profile, resolved)
        digest = _resonance_digest(
            family_id,
            profile["chip_id"],
            profile["profile_id"],
            profile_graph_hash,
            as_of,
            input_fingerprint,
            branch_generation,
            family["lineage_revisions"],
            family["provenance"],
            rows,
        )
        family_digests.append(digest)
        family_reports.append(
            {
                "family_id": family_id,
                "chip_id": profile["chip_id"],
                "alias": profile["alias"],
                "profile_id": profile["profile_id"],
                "nominal_hz": _effective_nominal_header(profile, resolved),
                "reading_count": len(rows),
                "readings": rows,
                "weighted_mean_ppm": _weighted_mean_ppm(rows),
                "branch_generation": branch_generation,
                "source_provenance": family["provenance"],
                "resonance_digest": digest,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "as_of_date": as_of,
        "input_fingerprint": input_fingerprint,
        "profile_graph_hash": profile_graph_hash,
        "batch_generation": batch_generation,
        "family_count": len(family_reports),
        "families": family_reports,
        "batch_digest": _batch_digest(
            as_of,
            input_fingerprint,
            profile_graph_hash,
            batch_generation,
            family_digests,
        ),
    }


def _write_chip(
    path: Path,
    family_id: str,
    chip_id: str,
    profile_id: str,
    nominal_hz: float,
    rows: list[tuple[str, int, float, float]],
    alias: str = "",
    segment_directives: dict[str, dict[str, float]] | None = None,
) -> None:
    body = [
        f"family_id={family_id}",
        f"chip_id={chip_id}",
        f"profile_id={profile_id}",
        f"nominal_hz={nominal_hz}",
    ]
    if alias:
        body.append(f"alias={alias}")
    body.append("readings:")
    current_segment = ""
    directives = segment_directives or {}
    for segment_id, line_index, temp_c, freq_hz in rows:
        if segment_id != current_segment:
            body.append(f"segment: {segment_id}")
            current_segment = segment_id
            for key, value in directives.get(segment_id, {}).items():
                body.append(f"{key}={value}")
        body.append(f"{line_index} {temp_c} {freq_hz}")
    path.write_text("\n".join(body) + "\n")


def _measured_hz(freq_25_hz: float, temp_c: float, alpha: float) -> float:
    return freq_25_hz * (1.0 + alpha * (temp_c - 25.0))


def _clean_output_dir() -> None:
    shutil.rmtree(OUT_DIR, ignore_errors=True)


def _run(
    chip_paths: list[Path],
    out: Path,
    as_of: str = DEFAULT_AS_OF,
) -> subprocess.CompletedProcess:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["/app/environment/bin/piezo-audit"]
    for path in chip_paths:
        cmd.extend(["--chip", str(path)])
    cmd.extend(["--as-of", as_of, "--out", str(out)])
    return subprocess.run(
        cmd,
        cwd=APP,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _rebuild() -> None:
    rebuild()


@pytest.fixture(autouse=True)
def _clean_output() -> None:
    _clean_output_dir()


def test_readings_sorted_by_temp_then_line_index(tmp_path: Path) -> None:
    """Readings and digest rows sort by (temp_c, line_index) ascending."""
    chip = tmp_path / "sort.chip"
    nominal = 5_000_000.0
    alpha = 35e-6
    _write_chip(
        chip,
        "FAM-SORT",
        "SORT-1",
        "CAL-STD",
        nominal,
        [
            ("default", 9, 35.0, _measured_hz(nominal, 35.0, alpha)),
            ("default", 2, 25.0, nominal),
            ("default", 7, 25.0, nominal + 1.0),
            ("default", 1, 15.0, _measured_hz(nominal, 15.0, alpha)),
        ],
    )
    out = tmp_path / "sort.json"
    expected = _expected_report([chip], "2024-07-01")
    proc = _run([chip], out, "2024-07-01")
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    temps = [row["temp_c"] for row in report["families"][0]["readings"]]
    assert temps == sorted(temps)
    assert report["families"][0]["readings"][1]["line_index"] == 2
    assert report["families"][0]["readings"][2]["line_index"] == 7
    keys = [(row["temp_c"], row["line_index"]) for row in report["families"][0]["readings"]]
    assert keys == sorted(keys)


def test_rounding_half_away_cliff(tmp_path: Path) -> None:
    """Four-decimal half-away-from-zero rounding affects ppm_pull and digest binding."""
    chip = tmp_path / "cliff.chip"
    nominal = 1_000_000.0
    _write_chip(
        chip,
        "FAM-CLIFF",
        "CLIFF-1",
        "CAL-STD",
        nominal,
        [
            ("edge", 1, 25.0, nominal),
            ("edge", 2, 25.0, 999_998.76543),
            ("edge", 3, 30.0, 1_000_123.45678),
        ],
    )
    out = tmp_path / "cliff.json"
    expected = _expected_report([chip], "2024-07-01")
    proc = _run([chip], out, "2024-07-01")
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    rows = report["families"][0]["readings"]
    assert rows[0]["ppm_pull"] == 0.0
    assert rows[1]["ppm_pull"] == _round4(-1.2346)
    assert rows[1]["freq_25_hz"] == _round4(999_998.7654)


def test_profile_nominal_override(tmp_path: Path) -> None:
    """Profile nominal_hz_override replaces chip nominal for ppm pull."""
    chip = tmp_path / "nominal_ov.chip"
    _write_chip(
        chip,
        "FAM-NOM",
        "NOM-1",
        "CAL-HIGH",
        9_000_000.0,
        [("default", 1, 25.0, 8_000_100.0)],
    )
    out = tmp_path / "nominal_ov.json"
    expected = _expected_report([chip], "2024-07-01")
    proc = _run([chip], out, "2024-07-01")
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    row = report["families"][0]["readings"][0]
    assert report["families"][0]["nominal_hz"] == 8_000_100.0
    assert row["ppm_pull"] == 0.0


def test_alias_chain_segment_provenance(tmp_path: Path) -> None:
    """Alias collision rewriting and segment_ids preserve CLI and segment order."""
    first = tmp_path / "trail_a.chip"
    second = tmp_path / "trail_b.chip"
    _write_chip(
        first,
        "FAM-TRAIL",
        "TRAIL-1",
        "CAL-STD",
        7_000_000.0,
        [("alpha", 5, 25.0, 7_000_000.0), ("beta", 1, 30.0, 7_001_225.0)],
        alias="SHARED-LABEL",
    )
    _write_chip(
        second,
        "FAM-TRAIL",
        "TRAIL-2",
        "CAL-STD",
        7_100_000.0,
        [("gamma", 1, 25.0, 7_100_000.0)],
        alias="SHARED-LABEL",
    )
    paths = [first, second]
    out = tmp_path / "trail.json"
    expected = _expected_report(paths)
    proc = _run(paths, out)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    prov = report["families"][0]["source_provenance"]
    assert prov[0]["alias"] == "SHARED-LABEL@TRAIL-1"
    assert prov[0]["segment_ids"] == ["alpha", "beta"]
    assert prov[1]["alias"] == "SHARED-LABEL"
    assert prov[1]["segment_ids"] == ["gamma"]


def test_multi_family_batch_sorted(tmp_path: Path) -> None:
    """Batch families[] are sorted by family_id ascending."""
    chip_a = tmp_path / "mf_a.chip"
    chip_b = tmp_path / "mf_b.chip"
    _write_chip(chip_a, "FAM-Z", "MF-Z", "CAL-STD", 4_000_000.0, [("default", 1, 25.0, 4_000_000.0)])
    _write_chip(chip_b, "FAM-A", "MF-A", "CAL-STD", 3_000_000.0, [("default", 1, 25.0, 3_000_000.0)])
    paths = [chip_a, chip_b]
    out = tmp_path / "mf.json"
    expected = _expected_report(paths)
    proc = _run(paths, out)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    assert [family["family_id"] for family in report["families"]] == ["FAM-A", "FAM-Z"]


def test_profile_inheritance_resolves_alpha(tmp_path: Path) -> None:
    """CAL-STD inherits alpha from CAL-BASE when its revision omits alpha."""
    chip = tmp_path / "inherit.chip"
    nominal = 12_000_000.0
    alpha = 3.5e-5
    _write_chip(
        chip,
        "FAM-INH",
        "INH-1",
        "CAL-STD",
        nominal,
        [
            ("default", 1, 25.0, nominal),
            ("default", 2, 30.0, _measured_hz(nominal, 30.0, alpha)),
        ],
    )
    out = tmp_path / "inherit.json"
    expected = _expected_report([chip], "2024-04-01")
    proc = _run([chip], out, "2024-04-01")
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    prov = report["families"][0]["source_provenance"][0]
    assert prov["profile_effective_date"] == "2024-01-01"
    assert prov["profile_parent_effective_date"] == "2024-01-01"
    lineage = expected["families"][0]["source_provenance"]
    assert lineage[0]["profile_parent_effective_date"] == "2024-01-01"


def test_deprecation_window_keeps_older_revision(tmp_path: Path) -> None:
    """Before a newer revision is effective, the older revision remains selected."""
    chip = tmp_path / "depr.chip"
    nominal = 11_000_000.0
    alpha_old = 3.5e-5
    _write_chip(
        chip,
        "FAM-DEPR",
        "DEPR-1",
        "CAL-STD",
        nominal,
        [
            ("default", 1, 25.0, nominal),
            ("default", 2, 30.0, _measured_hz(nominal, 30.0, alpha_old)),
        ],
    )
    out_early = tmp_path / "early.json"
    out_late = tmp_path / "late.json"
    early = _expected_report([chip], "2024-04-01")
    proc_e = _run([chip], out_early, "2024-04-01")
    assert proc_e.returncode == 0, proc_e.stderr
    assert json.loads(out_early.read_text()) == early
    assert early["families"][0]["source_provenance"][0]["profile_effective_date"] == "2024-01-01"

    late = _expected_report([chip], "2024-07-01", _read_manifest())
    proc_l = _run([chip], out_late, "2024-07-01")
    assert proc_l.returncode == 0, proc_l.stderr
    late_report = json.loads(out_late.read_text())
    assert late_report == late
    assert late_report["families"][0]["source_provenance"][0]["profile_effective_date"] == "2024-06-01"
    assert early["profile_graph_hash"] != late["profile_graph_hash"]


def test_segment_calibration_override(tmp_path: Path) -> None:
    """Segment alpha_override replaces profile alpha for that segment only."""
    chip = tmp_path / "segov.chip"
    nominal = 10_000_000.0
    _write_chip(
        chip,
        "FAM-SEG",
        "SEG-OV-1",
        "CAL-STD",
        nominal,
        [
            ("hot", 1, 35.0, 10_050_000.0),
            ("cold", 2, 25.0, nominal),
        ],
        segment_directives={"hot": {"alpha_override": 0.00005}},
    )
    out = tmp_path / "segov.json"
    expected = _expected_report([chip], "2024-07-01")
    proc = _run([chip], out, "2024-07-01")
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    hot = next(row for row in report["families"][0]["readings"] if row["segment_id"] == "hot")
    cold = next(row for row in report["families"][0]["readings"] if row["segment_id"] == "cold")
    assert hot["freq_25_hz"] == _round4(10_050_000.0 / (1.0 + 0.00005 * 10.0))
    assert cold["freq_25_hz"] == nominal


def test_alias_collision_resolution(tmp_path: Path) -> None:
    """Earlier alias collisions rewrite provenance alias to alias@chip_id."""
    first = tmp_path / "alias_a.chip"
    second = tmp_path / "alias_b.chip"
    _write_chip(
        first,
        "FAM-AL-1",
        "AL-1",
        "CAL-STD",
        6_000_000.0,
        [("default", 1, 25.0, 6_000_000.0)],
        alias="DUP-LABEL",
    )
    _write_chip(
        second,
        "FAM-AL-2",
        "AL-2",
        "CAL-STD",
        6_100_000.0,
        [("default", 1, 25.0, 6_100_000.0)],
        alias="DUP-LABEL",
    )
    paths = [first, second]
    out = tmp_path / "alias.json"
    expected = _expected_report(paths)
    proc = _run(paths, out)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    aliases = {
        entry["chip_id"]: entry["alias"]
        for family in report["families"]
        for entry in family["source_provenance"]
    }
    assert aliases["AL-1"] == "DUP-LABEL@AL-1"
    assert aliases["AL-2"] == "DUP-LABEL"


def test_merge_last_file_wins_per_family(tmp_path: Path) -> None:
    """Within a family, later --chip files replace (chip_id, profile_id) readings."""
    early = tmp_path / "early.chip"
    late = tmp_path / "late.chip"
    _write_chip(
        early,
        "FAM-PZ-A",
        "MRG-1",
        "CAL-STD",
        8_000_000.0,
        [("bench", 1, 25.0, 8_000_000.0), ("bench", 2, 35.0, 8_00117.84)],
        alias="EARLY",
    )
    _write_chip(
        late,
        "FAM-PZ-A",
        "MRG-1",
        "CAL-STD",
        8_000_100.0,
        [("bench", 1, 25.0, 8_000_100.0), ("bench", 2, 20.0, 7_999_940.32)],
        alias="LATE",
    )
    paths = [early, late]
    out = tmp_path / "merge.json"
    expected = _expected_report(paths)
    proc = _run(paths, out)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    family = report["families"][0]
    assert family["alias"] == "LATE"
    assert family["nominal_hz"] == 8_000_100.0
    assert len(family["source_provenance"]) == 2


def test_manifest_branch_rollback_reuse(tmp_path: Path) -> None:
    """Rollback to a prior batch key reuses batch_generation and branch_generation."""
    chip = tmp_path / "rb.chip"
    nominal = 7_500_000.0
    _write_chip(
        chip,
        "FAM-RB",
        "RB-1",
        "CAL-STD",
        nominal,
        [("default", 1, 25.0, nominal)],
    )
    out = tmp_path / "rb.json"
    assert _run([chip], out, "2024-07-01").returncode == 0
    first = json.loads(out.read_text())
    first_batch = first["batch_generation"]
    first_branch = first["families"][0]["branch_generation"]

    assert _run([chip], out, "2024-02-01").returncode == 0
    second = json.loads(out.read_text())
    assert second["batch_generation"] != first_batch

    assert _run([chip], out, "2024-07-01").returncode == 0
    third = json.loads(out.read_text())
    assert third["batch_generation"] == first_batch
    assert third["families"][0]["branch_generation"] == first_branch


def test_stale_cache_profile_graph_ignored(tmp_path: Path) -> None:
    """Cache rows must match both fingerprint and profile_graph_hash."""
    chip = tmp_path / "cache.chip"
    nominal = 4_000_000.0
    _write_chip(
        chip,
        "FAM-C",
        "CACHE",
        "CAL-STD",
        nominal,
        [("default", 1, 25.0, nominal), ("default", 2, 40.0, _measured_hz(nominal, 40.0, 35e-6))],
    )
    expected = _expected_report([chip], "2024-07-01")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stale_hash = "sha256:" + hashlib.sha256(b"stale-profile-graph").hexdigest()
    CACHE.write_text(
        json.dumps(
            {
                "input_fingerprint": expected["input_fingerprint"],
                "profile_graph_hash": stale_hash,
                "families": {
                    "FAM-C": expected["families"][0]["readings"][:1],
                },
            },
            indent=2,
        )
        + "\n"
    )
    out = tmp_path / "cache.json"
    proc = _run([chip], out, "2024-07-01")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text()) == expected


def test_fatal_error_preserves_manifest(tmp_path: Path) -> None:
    """Fatal parse errors delete --out but keep manifest intact."""
    good = tmp_path / "good.chip"
    _write_chip(good, "FAM-OK", "OK-1", "CAL-STD", 5_000_000.0, [("default", 1, 25.0, 5_000_000.0)])
    out = tmp_path / "out.json"
    assert _run([good], out).returncode == 0
    manifest_before = _read_manifest()
    bad = tmp_path / "bad.chip"
    bad.write_text("family_id=BAD\nchip_id=BAD\nprofile_id=CAL-STD\nnominal_hz=10\nreadings:\n")
    out.write_text('{"schema_version":4}')
    assert _run([bad], out).returncode != 0
    with pytest.raises(FileNotFoundError):
        out.read_text()
    assert json.loads(MANIFEST.read_text()) == manifest_before


def _assert_golden_digest_case(case: str, tmp_path: Path) -> None:
    """Public golden vectors for canonical digest serialization."""
    data = json.loads((GOLDEN / f"{case}.json").read_text())
    paths = [FIXTURES / Path(chip_path).name for chip_path in data["chip_paths"]]
    as_of = data["as_of_date"]
    out = tmp_path / f"{case}.json"
    _clean_output_dir()
    expected = _expected_report(paths, as_of, None)
    proc = _run(paths, out, as_of)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    assert report["input_fingerprint"] == data["input_fingerprint"]
    assert report["profile_graph_hash"] == data["profile_graph_hash"]
    assert report["batch_digest"] == data["batch_digest"]
    assert report["batch_generation"] == data["batch_generation"]
    assert report["family_count"] == data["family_count"]

    merged = _merge_batch(paths, as_of)
    pgh_body = _profile_graph_hash_body(
        merged["all_revisions"], merged["all_segment_overrides"]
    )
    assert pgh_body == data["profile_graph_hash_body"]

    family_digests: list[str] = []
    golden_by_id = {entry["family_id"]: entry for entry in data["families"]}
    for family in report["families"]:
        golden = golden_by_id[family["family_id"]]
        assert family["branch_generation"] == golden["branch_generation"]
        assert family["resonance_digest"] == golden["resonance_digest"]
        family_digests.append(family["resonance_digest"])

        family_merged = merged["families"][family["family_id"]]
        profile = family_merged["profile"]
        rows = _rows_from_profile(profile, family_merged["resolved"])
        payload = _resonance_digest_body(
            family["family_id"],
            profile["chip_id"],
            profile["profile_id"],
            report["profile_graph_hash"],
            as_of,
            report["input_fingerprint"],
            family["branch_generation"],
            family_merged["lineage_revisions"],
            family_merged["provenance"],
            rows,
        )
        assert payload == golden["payload"]

    batch_payload = _batch_digest_body(
        as_of,
        report["input_fingerprint"],
        report["profile_graph_hash"],
        report["batch_generation"],
        family_digests,
    )
    assert batch_payload == data["batch_digest_payload"]


def test_golden_single_family_digest_payload(tmp_path: Path) -> None:
    """Bundled golden_single.chip matches published canonical digest vectors."""
    _assert_golden_digest_case("single_family", tmp_path)


def test_golden_multi_family_digest_payload(tmp_path: Path) -> None:
    """Bundled golden_multi_* chips match published canonical batch digest vectors."""
    _assert_golden_digest_case("multi_family", tmp_path)


def test_visible_fixtures_match_oracle(tmp_path: Path) -> None:
    """Bundled chip_a and chip_family_b batch must match the independent oracle."""
    paths = [FIXTURES / "chip_a.chip", FIXTURES / "chip_family_b.chip"]
    out = tmp_path / "visible.json"
    expected = _expected_report(paths, DEFAULT_AS_OF, _read_manifest())
    proc = _run(paths, out)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text()) == expected


def test_prewritten_static_json_cannot_pass(tmp_path: Path) -> None:
    """Hand-authored reports are replaced by derived output."""
    chip = tmp_path / "static.chip"
    nominal = 3_000_000.0
    _write_chip(chip, "FAM-S", "STATIC", "CAL-STD", nominal, [("default", 1, 25.0, nominal)])
    out = tmp_path / "static.json"
    bogus_fp = "sha256:" + hashlib.sha256(b"bogus-fp").hexdigest()
    bogus_dig = "sha256:" + hashlib.sha256(b"bogus-dig").hexdigest()
    out.write_text(
        json.dumps(
            {
                "schema_version": 4,
                "as_of_date": DEFAULT_AS_OF,
                "input_fingerprint": bogus_fp,
                "profile_graph_hash": bogus_fp,
                "batch_generation": 1,
                "family_count": 0,
                "families": [],
                "batch_digest": bogus_dig,
            }
        )
        + "\n"
    )
    expected = _expected_report([chip])
    proc = _run([chip], out)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report == expected
    assert report["batch_digest"] != bogus_dig


def test_dynamic_generated_corpus(tmp_path: Path) -> None:
    """Seeded runtime chips exercise segments, profiles, and digest rules."""
    rng = random.Random(0xC0FFEE)
    catalog = _load_catalog()
    base = tmp_path / "corpus"
    base.mkdir()
    as_of_choices = ["2024-02-01", "2024-04-01", "2024-07-01"]
    for index in range(12):
        family = f"FAM-{index:02d}"
        chip_id = f"CORP-{index:02d}"
        as_of = rng.choice(as_of_choices)
        valid_profiles = [
            pid
            for pid in ("CAL-STD", "CAL-HIGH")
            if any(
                rev["profile_id"] == pid and rev["effective_date"] <= as_of
                for rev in catalog
            )
        ]
        profile_id = rng.choice(valid_profiles)
        nominal = float(rng.randint(4_000_000, 20_000_000))
        revision = _select_revision(catalog, profile_id, as_of)
        resolved = _resolve_profile(catalog, revision, as_of)
        alpha = resolved["resolved_alpha"]
        rows: list[tuple[str, int, float, float]] = []
        segment_directives: dict[str, dict[str, float]] = {}
        for seg_index in range(rng.randint(1, 3)):
            seg = f"seg-{seg_index}"
            if rng.random() < 0.25:
                segment_directives[seg] = {
                    "alpha_override": round(alpha * 1.5, 10),
                }
            for line in range(1, rng.randint(2, 4)):
                temp = float(rng.choice([15, 20, 25, 30, 35]))
                delta = rng.uniform(-500.0, 500.0)
                nominal_use = (
                    resolved["resolved_nominal_override"]
                    if resolved["resolved_nominal_override"] > 0.0
                    else nominal
                )
                freq = _measured_hz(nominal_use + delta, temp, alpha)
                rows.append((seg, line, temp, freq))
        path = base / f"{chip_id}.chip"
        _write_chip(
            path,
            family,
            chip_id,
            profile_id,
            nominal,
            rows,
            alias=f"ALT-{index}",
            segment_directives=segment_directives,
        )
        expected = _expected_report([path], as_of, _read_manifest())
        out = base / f"{chip_id}.json"
        proc = _run([path], out, as_of)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(out.read_text()) == expected


def _discover_hidden_cases() -> dict[str, list[str]]:
    cases: dict[str, list[str]] = {}
    for path in sorted(HIDDEN.iterdir()):
        if path.is_dir():
            chips = sorted(
                child.relative_to(HIDDEN).as_posix()
                for child in path.glob("*.chip")
            )
            if chips:
                cases[path.name] = chips
        elif path.suffix == ".chip":
            cases[path.stem] = [path.name]
    valid: dict[str, list[str]] = {}
    for name, parts in cases.items():
        try:
            for part in parts:
                _parse_chip(HIDDEN / part)
        except ValueError:
            continue
        valid[name] = parts
    return valid


HIDDEN_CASES = _discover_hidden_cases()

HIDDEN_AS_OF = {
    "hidden_profile_pick": "2024-07-01",
    "hidden_deprecation": "2024-04-01",
}


@pytest.mark.parametrize("case", sorted(HIDDEN_CASES))
def test_hidden_chips_match_oracle(case: str, tmp_path: Path) -> None:
    """Hidden chip corpora must match the independent oracle."""
    paths = [HIDDEN / part for part in HIDDEN_CASES[case]]
    as_of = HIDDEN_AS_OF.get(case, DEFAULT_AS_OF)
    expected = _expected_report(paths, as_of, _read_manifest())
    out = tmp_path / f"{case}.json"
    proc = _run(paths, out, as_of)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text()) == expected
