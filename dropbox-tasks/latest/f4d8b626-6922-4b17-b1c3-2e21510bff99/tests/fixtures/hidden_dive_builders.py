"""Verifier-only OEL builders for hidden sigma/omega dive bundles (not in agent image)."""
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
    import json

    payload = {
        "expedition_id": expedition_id,
        "reports": [report_to_dict(r) for r in reports],
        "observations": [obs_to_dict(o) for o in observations],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def build_omega_hidden() -> tuple[list[Report], list[Observation]]:
    reports = [
        Report("om-east", "east_ridge", 1, 1, None, True),
        Report("om-west", "west_trench", 1, 1, None, True),
    ]
    observations = [
        Observation(
            "obs-o01",
            "east_ridge",
            "2024-06-01T08:00:00Z",
            "SEAFLOOR_SAMPLE",
            1500,
            "EAST-A",
            "sonar-e1",
        ),
        Observation(
            "obs-o02",
            "west_trench",
            "2024-06-01T08:30:00Z",
            "MAGNETIC_ANOMALY",
            1600,
            "WEST-B",
            "mag-w1",
        ),
        Observation(
            "obs-o03",
            "east_ridge",
            "2024-06-01T09:00:00Z",
            "HYDROTHERMAL_VENT",
            1700,
            "EAST-V",
            "temp-e2",
        ),
        Observation(
            "obs-o04",
            "west_trench",
            "2024-06-01T09:30:00Z",
            "BATHYMETRY",
            1800,
            "WEST-D",
            "depth-w2",
        ),
    ]
    return reports, observations


def build_sigma_hidden() -> tuple[list[Report], list[Observation]]:
    reports = [
        Report("sg-001", "deep_trench", 1, 1, None, True),
    ]
    observations = [
        Observation(
            "obs-s01",
            "deep_trench",
            "2024-05-01T06:00:00Z",
            "HYDROTHERMAL_VENT",
            4200,
            "SIGMA-V",
            "probe-x",
        ),
        Observation(
            "obs-s02",
            "deep_trench",
            "2024-05-01T07:00:00Z",
            "SEAFLOOR_SAMPLE",
            4100,
            "SIGMA-S",
            "probe-y",
        ),
    ]
    return reports, observations


def build_tie_hidden() -> tuple[list[Report], list[Observation]]:
    """Equal rank and revision in one lane — report_id ascending tie-break."""
    reports = [
        Report("tie-002", "abyssal_plain", 2, 5, None, True),
        Report("tie-001", "abyssal_plain", 2, 5, None, True),
    ]
    observations = [
        Observation(
            "obs-t01",
            "abyssal_plain",
            "2024-08-01T08:00:00Z",
            "BATHYMETRY",
            3000,
            "ABY-A",
            "depth-t1",
        ),
    ]
    return reports, observations


def build_kappa_hidden() -> tuple[list[Report], list[Observation]]:
    """Two hydrothermal vents plus observation in lane with no winning report."""
    reports = [
        Report("kp-main", "vent_lane", 1, 1, None, True),
    ]
    observations = [
        Observation(
            "obs-k1",
            "vent_lane",
            "2024-07-01T10:00:00Z",
            "HYDROTHERMAL_VENT",
            2200,
            "VENT-LATE",
            "temp-k1",
        ),
        Observation(
            "obs-k2",
            "vent_lane",
            "2024-07-01T09:00:00Z",
            "HYDROTHERMAL_VENT",
            2100,
            "VENT-EARLY",
            "temp-k2",
        ),
        Observation(
            "obs-k3",
            "unmapped_rift",
            "2024-07-01T11:00:00Z",
            "SEAFLOOR_SAMPLE",
            1800,
            "ORPHAN",
            "cam-k3",
        ),
    ]
    return reports, observations
