"""Build OEL dive bundles for bootstrap and verifier fixtures."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Report:
    report_id: str
    dive_lane: str
    confidence_rank: int
    revision: int
    supersedes: str | None
    calibration_valid: bool


@dataclass
class Observation:
    obs_id: str
    dive_lane: str
    timestamp_utc: str
    obs_type: str
    depth_m: int
    feature_code: str
    instrument_id: str


def report_to_dict(r: Report) -> dict[str, Any]:
    return asdict(r)


def obs_to_dict(o: Observation) -> dict[str, Any]:
    return asdict(o)


def write_bundle(path, expedition_id: str, reports: list[Report], observations: list[Observation]) -> None:
    payload = {
        "expedition_id": expedition_id,
        "reports": [report_to_dict(r) for r in reports],
        "observations": [obs_to_dict(o) for o in observations],
    }
    import json

    path.write_text(json.dumps(payload, indent=2) + "\n")


def build_alpha_reports() -> list[Report]:
    return [
        Report("nt-001", "north_trench", 3, 1, None, True),
        Report("nt-002", "north_trench", 2, 1, "nt-001", True),
        Report("nt-003", "north_trench", 2, 2, "nt-002", True),
        Report("sr-001", "south_ridge", 1, 1, None, False),
        Report("sr-002", "south_ridge", 2, 1, None, True),
    ]


def build_alpha_observations() -> list[Observation]:
    return [
        Observation("obs-001", "north_trench", "2024-03-01T08:00:00Z", "SEAFLOOR_SAMPLE", 1200, "SMPL-A", "sonar-1"),
        Observation("obs-002", "south_ridge", "2024-03-01T09:00:00Z", "MAGNETIC_ANOMALY", 800, "MAGN-B", "mag-2"),
        Observation("obs-003", "north_trench", "2024-03-01T10:00:00Z", "HYDROTHERMAL_VENT", 2100, "VENT-C", "temp-3"),
        Observation("obs-004", "south_ridge", "2024-03-01T11:00:00Z", "BATHYMETRY", 950, "BATH-D", "depth-4"),
        Observation("obs-005", "north_trench", "2024-03-01T12:00:00Z", "CORAL_REEF", 450, "CORL-E", "cam-5"),
    ]


def build_beta_reports() -> list[Report]:
    return [
        Report("bd-001", "mid_abyss", 1, 1, None, True),
        Report("bd-002", "mid_abyss", 1, 2, None, True),
    ]


def build_beta_observations() -> list[Observation]:
    return [
        Observation("obs-b01", "mid_abyss", "2024-04-01T08:00:00Z", "SEDIMENT_CORE", 3000, "CORE-A", "drill-1"),
        Observation("obs-b02", "mid_abyss", "2024-04-01T09:00:00Z", "HYDROTHERMAL_VENT", 3200, "VENT-B", "temp-2"),
    ]
