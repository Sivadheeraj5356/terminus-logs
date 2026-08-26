"""Reference expeditctl semantics for independent verifier recomputation."""
from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Any


def crc32_hex_lower(data: str) -> str:
    return format(zlib.crc32(data.encode()) & 0xFFFFFFFF, "08x")


def canonical_json_string(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ",".join(canonical_json_string(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        parts = [json.dumps(k) + ":" + canonical_json_string(value[k]) for k in keys]
        return "{" + ",".join(parts) + "}"
    return json.dumps(value)


def staging_bind(expedition_id: str, report_ids: list[str]) -> str:
    ids = sorted(report_ids)
    payload = {"expedition_id": expedition_id, "report_ids": ids}
    return crc32_hex_lower(canonical_json_string(payload))


def lane_bind(report_ids: list[str]) -> str:
    ids = sorted(report_ids)
    return crc32_hex_lower(";".join(ids) + ";")


def reconcile_bind(feature_links: list[dict[str, str]]) -> str:
    payload = [{"links_to": link["links_to"], "obs_id": link["obs_id"]} for link in feature_links]
    return crc32_hex_lower(canonical_json_string(payload))


def expedition_seal(atlas_witness: str, reconcile_bind_value: str) -> str:
    return crc32_hex_lower(f"{atlas_witness}|{reconcile_bind_value}")


def resolve_precedence(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {r.get("supersedes") for r in reports if r.get("supersedes")}
    survivors = [r for r in reports if r["report_id"] not in superseded]
    lanes: dict[str, list[dict[str, Any]]] = {}
    for rep in survivors:
        lanes.setdefault(rep["dive_lane"], []).append(rep)
    winners: list[dict[str, Any]] = []
    for lane_reports in lanes.values():
        best = sorted(
            lane_reports,
            key=lambda r: (r["confidence_rank"], -r["revision"], r["report_id"]),
        )[0]
        winners.append(best)
    return sorted(winners, key=lambda r: r["report_id"])


def reconcile_observations(
    resolved_reports: list[dict[str, Any]], observations: list[dict[str, Any]]
) -> dict[str, Any]:
    lane_cal = {r["dive_lane"]: r["calibration_valid"] for r in resolved_reports}
    surviving = [o for o in observations if lane_cal.get(o["dive_lane"], False)]
    surviving = sorted(surviving, key=lambda o: o["timestamp_utc"])
    vents = [o for o in surviving if o["obs_type"] == "HYDROTHERMAL_VENT"]
    anchor_obs_id = vents[0]["obs_id"] if vents else ""
    feature_links: list[dict[str, str]] = []
    for idx, obs in enumerate(surviving):
        if idx == 0:
            continue
        links_to = ""
        for prev in reversed(surviving[:idx]):
            if prev["dive_lane"] == obs["dive_lane"]:
                links_to = prev["obs_id"]
                break
        if not links_to:
            links_to = surviving[idx - 1]["obs_id"]
        feature_links.append({"obs_id": obs["obs_id"], "links_to": links_to})
    return {
        "anchor_obs_id": anchor_obs_id,
        "observation_count": len(surviving),
        "observations": surviving,
        "feature_links": feature_links,
        "replay_seq": 2,
        "reconcile_bind": reconcile_bind(feature_links),
    }


def atlas_witness(atlas_without_witness: dict[str, Any]) -> str:
    body = {
        k: v
        for k, v in atlas_without_witness.items()
        if k not in ("atlas_witness", "expedition_seal")
    }
    canonical = canonical_json_string(body)
    return format(zlib.crc32(canonical.encode()) & 0xFFFFFFFF, "08x")


def build_atlas(
    expedition_id: str,
    reconciled: dict[str, Any],
    dive_lanes: list[dict[str, Any]],
) -> dict[str, Any]:
    observations = sorted(reconciled["observations"], key=lambda o: o["obs_id"])
    lanes = sorted(dive_lanes, key=lambda r: r["dive_lane"])
    body = {
        "expedition_id": expedition_id,
        "anchor_obs_id": reconciled["anchor_obs_id"],
        "observation_count": reconciled["observation_count"],
        "observations": observations,
        "dive_lanes": lanes,
    }
    witness = atlas_witness(body)
    body["atlas_witness"] = witness
    body["expedition_seal"] = expedition_seal(witness, reconciled["reconcile_bind"])
    return body


def pipeline_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    resolved_reports = resolve_precedence(bundle["reports"])
    report_ids = [r["report_id"] for r in resolved_reports]
    all_report_ids = [r["report_id"] for r in bundle["reports"]]
    reconciled = reconcile_observations(resolved_reports, bundle["observations"])
    atlas = build_atlas(bundle["expedition_id"], reconciled, resolved_reports)
    return {
        "staging": {
            "expedition_id": bundle["expedition_id"],
            "report_count": len(bundle["reports"]),
            "observation_count": len(bundle["observations"]),
            "reports": bundle["reports"],
            "observations": bundle["observations"],
            "staging_bind": staging_bind(bundle["expedition_id"], all_report_ids),
        },
        "resolved": {
            "expedition_id": bundle["expedition_id"],
            "reports": resolved_reports,
            "replay_seq": 1,
            "lane_bind": lane_bind(report_ids),
        },
        "reconciled": {
            "expedition_id": bundle["expedition_id"],
            **reconciled,
        },
        "atlas": atlas,
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())
