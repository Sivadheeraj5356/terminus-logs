"""Copy and mutate runtime fixtures for lunar-regolith verifier tests."""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence


def _resolve_canonical_data() -> Path:
    candidates = [
        Path("/app/data"),
        Path(__file__).resolve().parent.parent / "environment" / "app" / "data",
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "solver_config.json").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate canonical solver data "
        "(tried /app/data and environment/app/data)"
    )


CANONICAL_DATA = _resolve_canonical_data()

MATERIAL_FIELDS = [
    "material_id",
    "density_kg_m3",
    "heat_capacity_c0_j_kg_k",
    "heat_capacity_c1_j_kg_k2",
    "heat_capacity_c2_j_kg_k3",
    "contact_conductivity_w_m_k",
    "conductivity_depth_gradient_per_m",
    "radiative_conductivity_w_m_k4",
    "surface_albedo",
    "surface_emissivity",
]

DEPTH_GRID_FIELDS = [
    "case_id",
    "cell_index",
    "top_depth_m",
    "bottom_depth_m",
    "material_id",
    "initial_temperature_k",
]

ILLUMINATION_FIELDS = [
    "case_id",
    "period_s",
    "solar_flux_w_m2",
    "geothermal_flux_w_m2",
    "conductivity_scale",
    "albedo_offset",
    "spinup_tolerance_k",
    "maximum_spinup_cycles",
]

FORCING_FIELDS = [
    "case_id",
    "interval_seq",
    "start_time_s",
    "end_time_s",
    "cos_incidence_start",
    "cos_incidence_end",
    "eclipse_profile_id",
]

ECLIPSE_FIELDS = [
    "eclipse_profile_id",
    "profile_time_s",
    "transmission_fraction",
]

BAND_FIELDS = [
    "band_id",
    "sample_index",
    "wavelength_um",
    "response",
]

OBSERVATION_FIELDS = [
    "observation_id",
    "case_id",
    "time_s",
    "band_id",
]


@dataclass(frozen=True)
class FixturePaths:
    """Paths into a temporary copy of the solver data tree."""

    root: Path
    data_dir: Path
    materials: Path
    depth_grid: Path
    illumination_cases: Path
    forcing_intervals: Path
    eclipse_profiles: Path
    radiometer_bands: Path
    observation_queries: Path
    inversion_queries: Path
    solver_config: Path


def copy_fixture_tree(dest: Path) -> FixturePaths:
    """Copy canonical /app/data (or local fallback) into dest/data."""
    data_dir = Path(dest) / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    shutil.copytree(CANONICAL_DATA, data_dir)
    return FixturePaths(
        root=Path(dest),
        data_dir=data_dir,
        materials=data_dir / "materials.csv",
        depth_grid=data_dir / "depth_grid.csv",
        illumination_cases=data_dir / "illumination_cases.csv",
        forcing_intervals=data_dir / "forcing_intervals.csv",
        eclipse_profiles=data_dir / "eclipse_profiles.csv",
        radiometer_bands=data_dir / "radiometer_bands.csv",
        observation_queries=data_dir / "observation_queries.csv",
        inversion_queries=data_dir / "inversion_queries.json",
        solver_config=data_dir / "solver_config.json",
    )


def write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def update_solver_config(paths: FixturePaths, **updates: Any) -> dict[str, Any]:
    payload = load_json(paths.solver_config)
    payload.update(updates)
    write_json(paths.solver_config, payload)
    return payload


def set_material_field(
    paths: FixturePaths,
    material_id: str,
    field: str,
    value: Any,
) -> None:
    rows = read_csv(paths.materials)
    found = False
    for row in rows:
        if row["material_id"] == material_id:
            row[field] = str(value)
            found = True
    if not found:
        raise KeyError(f"material_id {material_id!r} not found")
    write_csv(paths.materials, MATERIAL_FIELDS, rows)


def mutate_all_materials(paths: FixturePaths, **fields: Any) -> None:
    rows = read_csv(paths.materials)
    for row in rows:
        for key, value in fields.items():
            row[key] = str(value)
    write_csv(paths.materials, MATERIAL_FIELDS, rows)


def write_materials(
    paths: FixturePaths,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    write_csv(paths.materials, MATERIAL_FIELDS, rows)


def write_depth_grid(
    paths: FixturePaths,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    write_csv(paths.depth_grid, DEPTH_GRID_FIELDS, rows)


def write_illumination_cases(
    paths: FixturePaths,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    write_csv(paths.illumination_cases, ILLUMINATION_FIELDS, rows)


def set_illumination_field(
    paths: FixturePaths,
    case_id: str,
    field: str,
    value: Any,
) -> None:
    rows = read_csv(paths.illumination_cases)
    found = False
    for row in rows:
        if row["case_id"] == case_id:
            row[field] = str(value)
            found = True
    if not found:
        raise KeyError(f"case_id {case_id!r} not found")
    write_csv(paths.illumination_cases, ILLUMINATION_FIELDS, rows)


def write_forcing_intervals(
    paths: FixturePaths,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    write_csv(paths.forcing_intervals, FORCING_FIELDS, rows)


def write_eclipse_profiles(
    paths: FixturePaths,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    write_csv(paths.eclipse_profiles, ECLIPSE_FIELDS, rows)


def set_eclipse_point(
    paths: FixturePaths,
    profile_id: str,
    profile_time_s: float,
    transmission_fraction: float,
) -> None:
    rows = read_csv(paths.eclipse_profiles)
    updated = False
    for row in rows:
        if (
            row["eclipse_profile_id"] == profile_id
            and abs(float(row["profile_time_s"]) - profile_time_s) < 1.0e-12
        ):
            row["transmission_fraction"] = str(transmission_fraction)
            updated = True
    if not updated:
        rows.append(
            {
                "eclipse_profile_id": profile_id,
                "profile_time_s": profile_time_s,
                "transmission_fraction": transmission_fraction,
            }
        )
    write_csv(paths.eclipse_profiles, ECLIPSE_FIELDS, rows)


def write_radiometer_bands(
    paths: FixturePaths,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    write_csv(paths.radiometer_bands, BAND_FIELDS, rows)


def scale_band_responses(
    paths: FixturePaths,
    band_id: str,
    factor: float,
) -> None:
    rows = read_csv(paths.radiometer_bands)
    for row in rows:
        if row["band_id"] == band_id:
            row["response"] = str(float(row["response"]) * factor)
    write_csv(paths.radiometer_bands, BAND_FIELDS, rows)


def write_observation_queries(
    paths: FixturePaths,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    write_csv(paths.observation_queries, OBSERVATION_FIELDS, rows)


def write_inversion_queries(
    paths: FixturePaths,
    fits: Sequence[Mapping[str, Any]],
) -> None:
    write_json(paths.inversion_queries, {"fits": list(fits)})


def clear_inversions(paths: FixturePaths) -> None:
    write_inversion_queries(paths, [])


def keep_cases(paths: FixturePaths, case_ids: Iterable[str]) -> None:
    """Retain only the listed illumination cases across related tables."""
    wanted = set(case_ids)
    for path, fields, key in (
        (paths.illumination_cases, ILLUMINATION_FIELDS, "case_id"),
        (paths.depth_grid, DEPTH_GRID_FIELDS, "case_id"),
        (paths.forcing_intervals, FORCING_FIELDS, "case_id"),
        (paths.observation_queries, OBSERVATION_FIELDS, "case_id"),
    ):
        rows = [row for row in read_csv(path) if row[key] in wanted]
        write_csv(path, fields, rows)

    payload = load_json(paths.inversion_queries)
    fits = payload.get("fits", payload) if isinstance(payload, dict) else payload
    write_inversion_queries(
        paths,
        [fit for fit in fits if fit["case_id"] in wanted],
    )


def write_uniform_depth_grid(
    paths: FixturePaths,
    *,
    case_id: str,
    cell_count: int,
    thickness_m: float,
    material_id: str,
    initial_temperature_k: float | Sequence[float],
) -> None:
    if isinstance(initial_temperature_k, (int, float)):
        temperatures = [float(initial_temperature_k)] * cell_count
    else:
        temperatures = [float(value) for value in initial_temperature_k]
        if len(temperatures) != cell_count:
            raise ValueError("initial_temperature_k length must match cell_count")
    rows = []
    for index in range(cell_count):
        rows.append(
            {
                "case_id": case_id,
                "cell_index": index,
                "top_depth_m": index * thickness_m,
                "bottom_depth_m": (index + 1) * thickness_m,
                "material_id": material_id,
                "initial_temperature_k": temperatures[index],
            }
        )
    write_depth_grid(paths, rows)


def write_constant_forcing(
    paths: FixturePaths,
    *,
    case_id: str,
    period_s: float,
    cos_incidence: float,
    eclipse_profile_id: str = "none",
) -> None:
    write_forcing_intervals(
        paths,
        [
            {
                "case_id": case_id,
                "interval_seq": 1,
                "start_time_s": 0.0,
                "end_time_s": period_s,
                "cos_incidence_start": cos_incidence,
                "cos_incidence_end": cos_incidence,
                "eclipse_profile_id": eclipse_profile_id,
            }
        ],
    )


def configure_micro_case(
    paths: FixturePaths,
    *,
    case_id: str = "case_micro",
    period_s: float = 600.0,
    time_step_s: float = 100.0,
    solar_flux_w_m2: float = 0.0,
    geothermal_flux_w_m2: float = 0.0,
    conductivity_scale: float = 1.0,
    albedo_offset: float = 0.0,
    spinup_tolerance_k: float = 1.0e-3,
    maximum_spinup_cycles: int = 5,
    cell_count: int = 3,
    thickness_m: float = 0.1,
    material_id: str = "lunar_regolith",
    initial_temperature_k: float | Sequence[float] = 200.0,
    cos_incidence: float = 0.0,
    eclipse_profile_id: str = "none",
    observation_times_s: Optional[Sequence[float]] = None,
    band_id: str = "band_8um",
    clear_fits: bool = True,
    material_overrides: Optional[Mapping[str, Any]] = None,
) -> None:
    """Rewrite the temp tree into a self-contained single-case scenario."""
    update_solver_config(paths, time_step_s=time_step_s)
    if material_overrides:
        mutate_all_materials(paths, **material_overrides)

    write_illumination_cases(
        paths,
        [
            {
                "case_id": case_id,
                "period_s": period_s,
                "solar_flux_w_m2": solar_flux_w_m2,
                "geothermal_flux_w_m2": geothermal_flux_w_m2,
                "conductivity_scale": conductivity_scale,
                "albedo_offset": albedo_offset,
                "spinup_tolerance_k": spinup_tolerance_k,
                "maximum_spinup_cycles": maximum_spinup_cycles,
            }
        ],
    )
    write_uniform_depth_grid(
        paths,
        case_id=case_id,
        cell_count=cell_count,
        thickness_m=thickness_m,
        material_id=material_id,
        initial_temperature_k=initial_temperature_k,
    )
    write_constant_forcing(
        paths,
        case_id=case_id,
        period_s=period_s,
        cos_incidence=cos_incidence,
        eclipse_profile_id=eclipse_profile_id,
    )

    if observation_times_s is None:
        observation_times_s = [period_s]
    write_observation_queries(
        paths,
        [
            {
                "observation_id": f"obs_{case_id}_{index}",
                "case_id": case_id,
                "time_s": time_s,
                "band_id": band_id,
            }
            for index, time_s in enumerate(observation_times_s)
        ],
    )
    if clear_fits:
        clear_inversions(paths)


def patch_rows(
    rows: Sequence[MutableMapping[str, Any]],
    *,
    match_key: str,
    match_value: str,
    updates: Mapping[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if str(item[match_key]) == match_value:
            for key, value in updates.items():
                item[key] = value
        out.append(item)
    return out
