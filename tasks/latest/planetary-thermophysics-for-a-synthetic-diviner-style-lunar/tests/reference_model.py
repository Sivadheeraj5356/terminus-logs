"""Independent offline reference for the lunar regolith 1D thermal model task."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class SolverConfig:
    stefan_boltzmann_w_m2_k4: float
    planck_constant_j_s: float
    boltzmann_constant_j_k: float
    speed_of_light_m_s: float
    time_step_s: float
    nonlinear_temperature_tolerance_k: float
    nonlinear_residual_tolerance_w_m2: float
    nonlinear_max_iterations: int
    line_search_min_factor: float
    minimum_temperature_k: float
    maximum_temperature_k: float
    energy_balance_tolerance_j_m2: float
    brightness_temperature_tolerance_k: float
    brightness_temperature_max_iterations: int
    inversion_parameter_tolerance: float
    inversion_objective_tolerance: float
    inversion_max_evaluations: int
    output_decimal_places: int


@dataclass(frozen=True)
class Material:
    material_id: str
    density_kg_m3: float
    heat_capacity_c0_j_kg_k: float
    heat_capacity_c1_j_kg_k2: float
    heat_capacity_c2_j_kg_k3: float
    contact_conductivity_w_m_k: float
    conductivity_depth_gradient_per_m: float
    radiative_conductivity_w_m_k4: float
    surface_albedo: float
    surface_emissivity: float


@dataclass(frozen=True)
class GridCell:
    case_id: str
    cell_index: int
    top_depth_m: float
    bottom_depth_m: float
    material_id: str
    initial_temperature_k: float

    @property
    def center_depth_m(self) -> float:
        return 0.5 * (self.top_depth_m + self.bottom_depth_m)

    @property
    def thickness_m(self) -> float:
        return self.bottom_depth_m - self.top_depth_m


@dataclass(frozen=True)
class IlluminationCase:
    case_id: str
    period_s: float
    solar_flux_w_m2: float
    geothermal_flux_w_m2: float
    conductivity_scale: float
    albedo_offset: float
    spinup_tolerance_k: float
    maximum_spinup_cycles: int


@dataclass(frozen=True)
class ForcingInterval:
    case_id: str
    interval_seq: int
    start_time_s: float
    end_time_s: float
    cos_incidence_start: float
    cos_incidence_end: float
    eclipse_profile_id: str


@dataclass(frozen=True)
class EclipsePoint:
    eclipse_profile_id: str
    profile_time_s: float
    transmission_fraction: float


@dataclass(frozen=True)
class BandSample:
    band_id: str
    sample_index: int
    wavelength_um: float
    response: float


@dataclass(frozen=True)
class ObservationQuery:
    observation_id: str
    case_id: str
    time_s: float
    band_id: str


@dataclass(frozen=True)
class InversionFit:
    fit_id: str
    case_id: str
    parameter_names: Tuple[str, ...]
    lower_bounds: Tuple[float, ...]
    upper_bounds: Tuple[float, ...]
    initial_values: Tuple[float, ...]
    observation_ids: Tuple[str, ...]
    target_brightness_temperatures_k: Tuple[float, ...]
    observation_weights: Tuple[float, ...]


@dataclass
class SolverData:
    config: SolverConfig
    materials: Dict[str, Material]
    grid_cells: Dict[str, List[GridCell]]
    illumination_cases: Dict[str, IlluminationCase]
    forcing_intervals: Dict[str, List[ForcingInterval]]
    eclipse_profiles: Dict[str, List[EclipsePoint]]
    radiometer_bands: Dict[str, List[BandSample]]
    observation_queries: List[ObservationQuery]
    inversion_fits: List[InversionFit]


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_solver_config(data_dir: Path) -> SolverConfig:
    payload = json.loads((data_dir / "solver_config.json").read_text(encoding="utf-8"))
    return SolverConfig(
        stefan_boltzmann_w_m2_k4=float(payload["stefan_boltzmann_w_m2_k4"]),
        planck_constant_j_s=float(payload["planck_constant_j_s"]),
        boltzmann_constant_j_k=float(payload["boltzmann_constant_j_k"]),
        speed_of_light_m_s=float(payload["speed_of_light_m_s"]),
        time_step_s=float(payload["time_step_s"]),
        nonlinear_temperature_tolerance_k=float(payload["nonlinear_temperature_tolerance_k"]),
        nonlinear_residual_tolerance_w_m2=float(payload["nonlinear_residual_tolerance_w_m2"]),
        nonlinear_max_iterations=int(payload["nonlinear_max_iterations"]),
        line_search_min_factor=float(payload["line_search_min_factor"]),
        minimum_temperature_k=float(payload["minimum_temperature_k"]),
        maximum_temperature_k=float(payload["maximum_temperature_k"]),
        energy_balance_tolerance_j_m2=float(payload["energy_balance_tolerance_j_m2"]),
        brightness_temperature_tolerance_k=float(payload["brightness_temperature_tolerance_k"]),
        brightness_temperature_max_iterations=int(payload["brightness_temperature_max_iterations"]),
        inversion_parameter_tolerance=float(payload["inversion_parameter_tolerance"]),
        inversion_objective_tolerance=float(payload["inversion_objective_tolerance"]),
        inversion_max_evaluations=int(payload["inversion_max_evaluations"]),
        output_decimal_places=int(payload["output_decimal_places"]),
    )


def load_solver_data(data_dir: Path | str) -> SolverData:
    root = Path(data_dir)
    config = load_solver_config(root)

    materials: Dict[str, Material] = {}
    for row in _read_csv(root / "materials.csv"):
        materials[row["material_id"]] = Material(
            material_id=row["material_id"],
            density_kg_m3=float(row["density_kg_m3"]),
            heat_capacity_c0_j_kg_k=float(row["heat_capacity_c0_j_kg_k"]),
            heat_capacity_c1_j_kg_k2=float(row["heat_capacity_c1_j_kg_k2"]),
            heat_capacity_c2_j_kg_k3=float(row["heat_capacity_c2_j_kg_k3"]),
            contact_conductivity_w_m_k=float(row["contact_conductivity_w_m_k"]),
            conductivity_depth_gradient_per_m=float(row["conductivity_depth_gradient_per_m"]),
            radiative_conductivity_w_m_k4=float(row["radiative_conductivity_w_m_k4"]),
            surface_albedo=float(row["surface_albedo"]),
            surface_emissivity=float(row["surface_emissivity"]),
        )

    grid_cells: Dict[str, List[GridCell]] = {}
    for row in _read_csv(root / "depth_grid.csv"):
        cell = GridCell(
            case_id=row["case_id"],
            cell_index=int(row["cell_index"]),
            top_depth_m=float(row["top_depth_m"]),
            bottom_depth_m=float(row["bottom_depth_m"]),
            material_id=row["material_id"],
            initial_temperature_k=float(row["initial_temperature_k"]),
        )
        grid_cells.setdefault(cell.case_id, []).append(cell)
    for case_id in grid_cells:
        grid_cells[case_id].sort(key=lambda cell: cell.cell_index)

    illumination_cases: Dict[str, IlluminationCase] = {}
    for row in _read_csv(root / "illumination_cases.csv"):
        case = IlluminationCase(
            case_id=row["case_id"],
            period_s=float(row["period_s"]),
            solar_flux_w_m2=float(row["solar_flux_w_m2"]),
            geothermal_flux_w_m2=float(row["geothermal_flux_w_m2"]),
            conductivity_scale=float(row["conductivity_scale"]),
            albedo_offset=float(row["albedo_offset"]),
            spinup_tolerance_k=float(row["spinup_tolerance_k"]),
            maximum_spinup_cycles=int(row["maximum_spinup_cycles"]),
        )
        illumination_cases[case.case_id] = case

    forcing_intervals: Dict[str, List[ForcingInterval]] = {}
    for row in _read_csv(root / "forcing_intervals.csv"):
        interval = ForcingInterval(
            case_id=row["case_id"],
            interval_seq=int(row["interval_seq"]),
            start_time_s=float(row["start_time_s"]),
            end_time_s=float(row["end_time_s"]),
            cos_incidence_start=float(row["cos_incidence_start"]),
            cos_incidence_end=float(row["cos_incidence_end"]),
            eclipse_profile_id=row["eclipse_profile_id"],
        )
        forcing_intervals.setdefault(interval.case_id, []).append(interval)
    for case_id in forcing_intervals:
        forcing_intervals[case_id].sort(key=lambda item: item.interval_seq)

    eclipse_profiles: Dict[str, List[EclipsePoint]] = {}
    for row in _read_csv(root / "eclipse_profiles.csv"):
        point = EclipsePoint(
            eclipse_profile_id=row["eclipse_profile_id"],
            profile_time_s=float(row["profile_time_s"]),
            transmission_fraction=float(row["transmission_fraction"]),
        )
        eclipse_profiles.setdefault(point.eclipse_profile_id, []).append(point)
    for profile_id in eclipse_profiles:
        eclipse_profiles[profile_id].sort(key=lambda item: item.profile_time_s)

    radiometer_bands: Dict[str, List[BandSample]] = {}
    for row in _read_csv(root / "radiometer_bands.csv"):
        sample = BandSample(
            band_id=row["band_id"],
            sample_index=int(row["sample_index"]),
            wavelength_um=float(row["wavelength_um"]),
            response=float(row["response"]),
        )
        radiometer_bands.setdefault(sample.band_id, []).append(sample)
    for band_id in radiometer_bands:
        radiometer_bands[band_id].sort(key=lambda item: item.sample_index)

    observation_queries = [
        ObservationQuery(
            observation_id=row["observation_id"],
            case_id=row["case_id"],
            time_s=float(row["time_s"]),
            band_id=row["band_id"],
        )
        for row in _read_csv(root / "observation_queries.csv")
    ]

    inversion_fits: List[InversionFit] = []
    inversion_path = root / "inversion_queries.json"
    if inversion_path.exists():
        payload = json.loads(inversion_path.read_text(encoding="utf-8"))
        fits = payload["fits"] if isinstance(payload, dict) else payload
        for fit in fits:
            inversion_fits.append(
                InversionFit(
                    fit_id=fit["fit_id"],
                    case_id=fit["case_id"],
                    parameter_names=tuple(fit["parameter_names"]),
                    lower_bounds=tuple(float(x) for x in fit["lower_bounds"]),
                    upper_bounds=tuple(float(x) for x in fit["upper_bounds"]),
                    initial_values=tuple(float(x) for x in fit["initial_values"]),
                    observation_ids=tuple(fit["observation_ids"]),
                    target_brightness_temperatures_k=tuple(
                        float(x) for x in fit["target_brightness_temperatures_k"]
                    ),
                    observation_weights=tuple(float(x) for x in fit["observation_weights"]),
                )
            )

    return SolverData(
        config=config,
        materials=materials,
        grid_cells=grid_cells,
        illumination_cases=illumination_cases,
        forcing_intervals=forcing_intervals,
        eclipse_profiles=eclipse_profiles,
        radiometer_bands=radiometer_bands,
        observation_queries=observation_queries,
        inversion_fits=inversion_fits,
    )


def clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def effective_albedo(material: Material, albedo_offset: float) -> float:
    return clamp(material.surface_albedo + albedo_offset, 0.0, 1.0)


def thermal_surface_emissivity(material: Material, case: IlluminationCase) -> float:
    # Surface radiation always uses the declared material emissivity. The spin-up
    # tolerance must never enable or disable physical radiation.
    _ = case
    return material.surface_emissivity


def heat_capacity(material: Material, temperature_k: float) -> float:
    return (
        material.heat_capacity_c0_j_kg_k
        + material.heat_capacity_c1_j_kg_k2 * temperature_k
        + material.heat_capacity_c2_j_kg_k3 * temperature_k * temperature_k
    )


def cell_energy(material: Material, thickness_m: float, temperature_k: float) -> float:
    rho = material.density_kg_m3
    c0 = material.heat_capacity_c0_j_kg_k
    c1 = material.heat_capacity_c1_j_kg_k2
    c2 = material.heat_capacity_c2_j_kg_k3
    t = temperature_k
    return rho * thickness_m * (c0 * t + 0.5 * c1 * t * t + (1.0 / 3.0) * c2 * t * t * t)


def cell_conductivity(
    material: Material,
    temperature_k: float,
    center_depth_m: float,
    conductivity_scale: float,
) -> float:
    return conductivity_scale * material.contact_conductivity_w_m_k * (
        1.0 + material.conductivity_depth_gradient_per_m * center_depth_m
    ) + material.radiative_conductivity_w_m_k4 * temperature_k**3


def interpolate_linear(
    times: Sequence[float],
    values: Sequence[float],
    query_time_s: float,
) -> float:
    if query_time_s <= times[0]:
        return values[0]
    if query_time_s >= times[-1]:
        return values[-1]
    for index in range(len(times) - 1):
        t0 = times[index]
        t1 = times[index + 1]
        if t0 <= query_time_s <= t1:
            if t1 == t0:
                return values[index + 1]
            fraction = (query_time_s - t0) / (t1 - t0)
            return values[index] + fraction * (values[index + 1] - values[index])
    return values[-1]


def cos_incidence_at_time(intervals: Sequence[ForcingInterval], time_s: float) -> float:
    local_time = time_s
    for interval in intervals:
        if interval.start_time_s <= local_time <= interval.end_time_s:
            span = interval.end_time_s - interval.start_time_s
            if span <= 0.0:
                cos_value = interval.cos_incidence_start
            else:
                fraction = (local_time - interval.start_time_s) / span
                cos_value = interval.cos_incidence_start + fraction * (
                    interval.cos_incidence_end - interval.cos_incidence_start
                )
            return max(0.0, cos_value)
    last = intervals[-1]
    return max(0.0, last.cos_incidence_end)


def eclipse_transmission_at_time(
    profiles: Mapping[str, List[EclipsePoint]],
    profile_id: str,
    time_s: float,
) -> float:
    if profile_id == "none":
        return 1.0
    points = profiles[profile_id]
    times = [point.profile_time_s for point in points]
    values = [point.transmission_fraction for point in points]
    return interpolate_linear(times, values, time_s)


def absorbed_solar_flux(
    case: IlluminationCase,
    material: Material,
    intervals: Sequence[ForcingInterval],
    profiles: Mapping[str, List[EclipsePoint]],
    time_s: float,
    albedo_offset: float,
) -> float:
    albedo = effective_albedo(material, albedo_offset)
    cos_value = cos_incidence_at_time(intervals, time_s)
    for interval in intervals:
        if interval.start_time_s <= time_s <= interval.end_time_s:
            transmission = eclipse_transmission_at_time(
                profiles, interval.eclipse_profile_id, time_s
            )
            return (1.0 - albedo) * case.solar_flux_w_m2 * cos_value * transmission
    interval = intervals[-1]
    transmission = eclipse_transmission_at_time(
        profiles, interval.eclipse_profile_id, time_s
    )
    return (1.0 - albedo) * case.solar_flux_w_m2 * cos_value * transmission


def planck_radiance(
    wavelength_m: float,
    temperature_k: float,
    config: SolverConfig,
) -> float:
    if temperature_k <= 0.0 or wavelength_m <= 0.0:
        return 0.0
    h = config.planck_constant_j_s
    c = config.speed_of_light_m_s
    k_b = config.boltzmann_constant_j_k
    exponent = h * c / (wavelength_m * k_b * temperature_k)
    if exponent > 700.0:
        return 0.0
    denom = math.expm1(exponent)
    if denom <= 0.0:
        return 0.0
    return (2.0 * h * c * c) / (wavelength_m**5 * denom)


def band_response_reference(samples: Sequence[BandSample]) -> float:
    if not samples:
        return 1.0
    return max((sample.response for sample in samples), default=1.0) or 1.0


def band_response_integral(samples: Sequence[BandSample]) -> float:
    reference = band_response_reference(samples)
    total = 0.0
    for index in range(len(samples) - 1):
        left = samples[index]
        right = samples[index + 1]
        delta_lambda_m = (right.wavelength_um - left.wavelength_um) * 1.0e-6
        total += 0.5 * (left.response / reference + right.response / reference) * delta_lambda_m
    return total * reference


def normalized_band_terms(
    samples: Sequence[BandSample],
    temperature_k: float,
    config: SolverConfig,
) -> tuple[float, float]:
    reference = band_response_reference(samples)
    weighted = 0.0
    response = 0.0
    for index in range(len(samples) - 1):
        left = samples[index]
        right = samples[index + 1]
        delta_lambda_m = (right.wavelength_um - left.wavelength_um) * 1.0e-6
        wavelength_left_m = left.wavelength_um * 1.0e-6
        wavelength_right_m = right.wavelength_um * 1.0e-6
        planck_left = planck_radiance(wavelength_left_m, temperature_k, config)
        planck_right = planck_radiance(wavelength_right_m, temperature_k, config)
        left_norm = left.response / reference
        right_norm = right.response / reference
        weighted += 0.5 * (left_norm * planck_left + right_norm * planck_right) * delta_lambda_m
        response += 0.5 * (left_norm + right_norm) * delta_lambda_m
    return weighted, response


def band_radiance(
    samples: Sequence[BandSample],
    temperature_k: float,
    emissivity: float,
    config: SolverConfig,
) -> float:
    weighted, response = normalized_band_terms(samples, temperature_k, config)
    if response <= 0.0:
        return 0.0
    return emissivity * weighted / response


def normalized_blackbody_integral(
    samples: Sequence[BandSample],
    temperature_k: float,
    config: SolverConfig,
) -> float:
    weighted, response = normalized_band_terms(samples, temperature_k, config)
    if response <= 0.0:
        return 0.0
    return weighted / response


def brightness_temperature(
    samples: Sequence[BandSample],
    observed_radiance: float,
    config: SolverConfig,
) -> float:
    if observed_radiance <= 0.0:
        return config.minimum_temperature_k
    target = observed_radiance
    low = config.minimum_temperature_k
    high = config.maximum_temperature_k
    f_low = normalized_blackbody_integral(samples, low, config) - target
    f_high = normalized_blackbody_integral(samples, high, config) - target
    if f_low * f_high > 0.0:
        return clamp(observed_radiance, low, high)
    for _ in range(config.brightness_temperature_max_iterations):
        mid = 0.5 * (low + high)
        f_mid = normalized_blackbody_integral(samples, mid, config) - target
        if abs(f_mid) <= config.brightness_temperature_tolerance_k:
            return mid
        if f_low * f_mid <= 0.0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid
    return 0.5 * (low + high)


class ThermalModel:
    def __init__(self, data: SolverData) -> None:
        self.data = data
        self.config = data.config

    def _clip_temperatures(self, temperatures: np.ndarray) -> np.ndarray:
        return np.clip(
            temperatures,
            self.config.minimum_temperature_k,
            self.config.maximum_temperature_k,
        )

    def _face_conductivity(
        self,
        cells: Sequence[GridCell],
        temperatures: np.ndarray,
        conductivity_scale: float,
        face_index: int,
    ) -> float:
        left_index = face_index
        right_index = face_index + 1
        left_cell = cells[left_index]
        right_cell = cells[right_index]
        left_material = self.data.materials[left_cell.material_id]
        right_material = self.data.materials[right_cell.material_id]
        k_left = cell_conductivity(
            left_material,
            float(temperatures[left_index]),
            left_cell.center_depth_m,
            conductivity_scale,
        )
        k_right = cell_conductivity(
            right_material,
            float(temperatures[right_index]),
            right_cell.center_depth_m,
            conductivity_scale,
        )
        z_face = left_cell.bottom_depth_m
        z_left = left_cell.center_depth_m
        z_right = right_cell.center_depth_m
        resistance = (z_face - z_left) / k_left + (z_right - z_face) / k_right
        if resistance <= 0.0:
            return 0.5 * (k_left + k_right)
        return (z_right - z_left) / resistance

    def _harmonic_flux(
        self,
        cells: Sequence[GridCell],
        temperatures: np.ndarray,
        conductivity_scale: float,
        face_index: int,
    ) -> float:
        left_index = face_index
        right_index = face_index + 1
        left_cell = cells[left_index]
        right_cell = cells[right_index]
        left_material = self.data.materials[left_cell.material_id]
        right_material = self.data.materials[right_cell.material_id]
        k_left = cell_conductivity(
            left_material,
            float(temperatures[left_index]),
            left_cell.center_depth_m,
            conductivity_scale,
        )
        k_right = cell_conductivity(
            right_material,
            float(temperatures[right_index]),
            right_cell.center_depth_m,
            conductivity_scale,
        )
        z_face = left_cell.bottom_depth_m
        z_left = left_cell.center_depth_m
        z_right = right_cell.center_depth_m
        denominator = (z_face - z_left) / k_left + (z_right - z_face) / k_right
        if denominator <= 0.0:
            return 0.0
        return (float(temperatures[left_index]) - float(temperatures[right_index])) / denominator

    def _surface_flux_down(
        self,
        case: IlluminationCase,
        material: Material,
        intervals: Sequence[ForcingInterval],
        time_s: float,
        surface_temperature_k: float,
        albedo_offset: float,
    ) -> Tuple[float, float, float]:
        q_solar = absorbed_solar_flux(
            case, material, intervals, self.data.eclipse_profiles, time_s, albedo_offset
        )
        q_emit = thermal_surface_emissivity(material, case) * self.config.stefan_boltzmann_w_m2_k4 * (
            surface_temperature_k**4
        )
        return q_solar - q_emit, q_solar, q_emit

    def _residuals(
        self,
        cells: Sequence[GridCell],
        case: IlluminationCase,
        intervals: Sequence[ForcingInterval],
        temperatures_new: np.ndarray,
        temperatures_old: np.ndarray,
        time_s: float,
        conductivity_scale: float,
        albedo_offset: float,
    ) -> Tuple[np.ndarray, float, float, float, float, float]:
        dt = self.config.time_step_s
        count = len(cells)
        residuals = np.zeros(count, dtype=float)
        surface_material = self.data.materials[cells[0].material_id]
        q_surface_down, q_solar, q_emit = self._surface_flux_down(
            case,
            surface_material,
            intervals,
            time_s,
            float(temperatures_new[0]),
            albedo_offset,
        )
        q_bottom_down = -case.geothermal_flux_w_m2

        for index in range(count):
            material = self.data.materials[cells[index].material_id]
            energy_old = cell_energy(material, cells[index].thickness_m, float(temperatures_old[index]))
            energy_new = cell_energy(material, cells[index].thickness_m, float(temperatures_new[index]))
            if index == 0:
                q_top = q_surface_down
            else:
                q_top = self._harmonic_flux(
                    cells, temperatures_new, conductivity_scale, index - 1
                )
            if index == count - 1:
                q_bottom = q_bottom_down
            else:
                q_bottom = self._harmonic_flux(
                    cells, temperatures_new, conductivity_scale, index
                )
            residuals[index] = (energy_new - energy_old) / dt - (q_top - q_bottom)

        conductive_surface = 0.0
        if count > 1:
            conductive_surface = self._harmonic_flux(
                cells, temperatures_new, conductivity_scale, 0
            )
        return residuals, q_solar, q_emit, conductive_surface, q_surface_down, q_bottom_down

    def solve_nonlinear_step(
        self,
        cells: Sequence[GridCell],
        case: IlluminationCase,
        intervals: Sequence[ForcingInterval],
        temperatures_old: np.ndarray,
        time_s: float,
        conductivity_scale: float,
        albedo_offset: float,
    ) -> Tuple[np.ndarray, int, float, Dict[str, float]]:
        temperatures = self._clip_temperatures(temperatures_old.copy())
        max_iterations = self.config.nonlinear_max_iterations
        max_residual = float("inf")
        iterations = 0
        fluxes: Dict[str, float] = {}

        for iteration in range(max_iterations):
            residuals, q_solar, q_emit, conductive_surface, q_surface_down, q_bottom_down = (
                self._residuals(
                    cells,
                    case,
                    intervals,
                    temperatures,
                    temperatures_old,
                    time_s,
                    conductivity_scale,
                    albedo_offset,
                )
            )
            max_residual = float(np.max(np.abs(residuals)))
            fluxes = {
                "absorbed_solar_flux_w_m2": q_solar,
                "emitted_thermal_flux_w_m2": q_emit,
                "conductive_flux_down_w_m2": conductive_surface,
                "geothermal_flux_up_w_m2": case.geothermal_flux_w_m2,
                "q_surface_down": q_surface_down,
                "q_bottom_down": q_bottom_down,
            }
            if max_residual <= self.config.nonlinear_residual_tolerance_w_m2:
                iterations = iteration + 1
                break

            jacobian = np.zeros((len(cells), len(cells)), dtype=float)
            delta_temperature = max(self.config.nonlinear_temperature_tolerance_k, 1.0e-6)
            for column in range(len(cells)):
                perturbed = temperatures.copy()
                step = delta_temperature * max(1.0, abs(float(perturbed[column])))
                perturbed[column] += step
                perturbed = self._clip_temperatures(perturbed)
                perturbed_residuals, _, _, _, _, _ = self._residuals(
                    cells,
                    case,
                    intervals,
                    perturbed,
                    temperatures_old,
                    time_s,
                    conductivity_scale,
                    albedo_offset,
                )
                jacobian[:, column] = (perturbed_residuals - residuals) / (
                    perturbed[column] - temperatures[column]
                )

            try:
                delta = np.linalg.solve(jacobian, -residuals)
            except np.linalg.LinAlgError:
                delta = -0.1 * residuals

            alpha = 1.0
            accepted = False
            while alpha >= self.config.line_search_min_factor:
                trial = self._clip_temperatures(temperatures + alpha * delta)
                trial_residuals, _, _, _, _, _ = self._residuals(
                    cells,
                    case,
                    intervals,
                    trial,
                    temperatures_old,
                    time_s,
                    conductivity_scale,
                    albedo_offset,
                )
                trial_max = float(np.max(np.abs(trial_residuals)))
                if trial_max < max_residual:
                    temperatures = trial
                    accepted = True
                    break
                alpha *= 0.5
            if not accepted:
                temperatures = self._clip_temperatures(temperatures - 0.05 * residuals)
            iterations = iteration + 1

        return temperatures, iterations, max_residual, fluxes

    def simulate_period(
        self,
        cells: Sequence[GridCell],
        case: IlluminationCase,
        intervals: Sequence[ForcingInterval],
        initial_temperatures: np.ndarray,
        conductivity_scale: float,
        albedo_offset: float,
        record: bool,
        start_time_s: float = 0.0,
    ) -> Dict[str, Any]:
        dt = self.config.time_step_s
        steps = int(round(case.period_s / dt))
        temperatures = self._clip_temperatures(initial_temperatures.copy())
        start_profile = temperatures.copy()
        time_step_rows: List[Dict[str, Any]] = []
        surface_flux_rows: List[Dict[str, Any]] = []
        temperature_history: Dict[float, np.ndarray] = {}

        for step_index in range(steps):
            start_time = start_time_s + step_index * dt
            end_time = start_time + dt
            old_temperatures = temperatures.copy()
            temperatures, nonlinear_iterations, max_residual, fluxes = self.solve_nonlinear_step(
                cells,
                case,
                intervals,
                old_temperatures,
                end_time,
                conductivity_scale,
                albedo_offset,
            )
            if record:
                temperature_history[end_time] = temperatures.copy()
                stored_change = 0.0
                for cell_index, cell in enumerate(cells):
                    material = self.data.materials[cell.material_id]
                    stored_change += cell_energy(
                        material, cell.thickness_m, float(temperatures[cell_index])
                    ) - cell_energy(
                        material, cell.thickness_m, float(old_temperatures[cell_index])
                    )
                net_boundary = dt * (fluxes["q_surface_down"] - fluxes["q_bottom_down"])
                energy_residual = stored_change - net_boundary
                time_step_rows.append(
                    {
                        "case_id": case.case_id,
                        "step_index": step_index,
                        "start_time_s": start_time,
                        "end_time_s": end_time,
                        "nonlinear_iterations": nonlinear_iterations,
                        "maximum_residual_w_m2": max_residual,
                        "converged": max_residual
                        <= self.config.nonlinear_residual_tolerance_w_m2,
                    }
                )
                surface_flux_rows.append(
                    {
                        "case_id": case.case_id,
                        "step_index": step_index,
                        "end_time_s": end_time,
                        "absorbed_solar_flux_w_m2": fluxes["absorbed_solar_flux_w_m2"],
                        "emitted_thermal_flux_w_m2": fluxes["emitted_thermal_flux_w_m2"],
                        "conductive_flux_down_w_m2": fluxes["conductive_flux_down_w_m2"],
                        "geothermal_flux_up_w_m2": fluxes["geothermal_flux_up_w_m2"],
                        "stored_energy_change_j_m2": stored_change,
                        "net_boundary_energy_j_m2": net_boundary,
                        "energy_residual_j_m2": energy_residual,
                    }
                )

        cycle_difference = float(np.max(np.abs(temperatures - start_profile)))
        return {
            "final_temperatures": temperatures,
            "cycle_difference_k": cycle_difference,
            "time_step_rows": time_step_rows,
            "surface_flux_rows": surface_flux_rows,
            "temperature_history": temperature_history,
        }

    def run_forward_case(
        self,
        case_id: str,
        conductivity_scale: Optional[float] = None,
        albedo_offset: Optional[float] = None,
        maximum_spinup_cycles: Optional[int] = None,
    ) -> Dict[str, Any]:
        case = self.data.illumination_cases[case_id]
        cells = self.data.grid_cells[case_id]
        intervals = self.data.forcing_intervals[case_id]
        scale = case.conductivity_scale if conductivity_scale is None else conductivity_scale
        offset = case.albedo_offset if albedo_offset is None else albedo_offset
        max_cycles = (
            case.maximum_spinup_cycles
            if maximum_spinup_cycles is None
            else maximum_spinup_cycles
        )

        # Public spin-up contract: start from the grid initial profile only.
        # No hidden steady-state warm-start (singular for ε=0 night/geo cases).
        temperatures = self._clip_temperatures(
            np.array([cell.initial_temperature_k for cell in cells], dtype=float)
        )
        spinup_cycles = 0
        final_spinup_difference = float("inf")
        while spinup_cycles < max_cycles:
            spinup_cycles += 1
            period_result = self.simulate_period(
                cells,
                case,
                intervals,
                temperatures,
                scale,
                offset,
                record=False,
            )
            temperatures = period_result["final_temperatures"]
            final_spinup_difference = period_result["cycle_difference_k"]
            if final_spinup_difference <= case.spinup_tolerance_k:
                break
        else:
            raise RuntimeError(
                f"spin-up failed for {case_id} after {max_cycles} cycles"
            )

        report_result = self.simulate_period(
            cells,
            case,
            intervals,
            temperatures,
            scale,
            offset,
            record=True,
        )
        return {
            "case_id": case_id,
            "cells": cells,
            "spinup_cycles": spinup_cycles,
            "final_spinup_difference_k": final_spinup_difference,
            "time_step_rows": report_result["time_step_rows"],
            "surface_flux_rows": report_result["surface_flux_rows"],
            "temperature_history": report_result["temperature_history"],
            "conductivity_scale": scale,
            "albedo_offset": offset,
        }


def observation_lookup(data: SolverData) -> Dict[str, ObservationQuery]:
    return {query.observation_id: query for query in data.observation_queries}


def build_temperature_rows(
    data: SolverData,
    case_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    case_id = case_result["case_id"]
    cells = case_result["cells"]
    history = case_result["temperature_history"]
    for query in data.observation_queries:
        if query.case_id != case_id:
            continue
        if query.time_s not in history:
            continue
        temperatures = history[query.time_s]
        for cell in cells:
            rows.append(
                {
                    "case_id": case_id,
                    "observation_id": query.observation_id,
                    "time_s": query.time_s,
                    "cell_index": cell.cell_index,
                    "depth_center_m": cell.center_depth_m,
                    "temperature_k": float(temperatures[cell.cell_index]),
                }
            )
    rows.sort(
        key=lambda row: (row["case_id"], row["observation_id"], row["cell_index"])
    )
    return rows


def build_radiometer_rows(
    data: SolverData,
    case_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    case_id = case_result["case_id"]
    history = case_result["temperature_history"]
    surface_material = data.materials[case_result["cells"][0].material_id]
    for query in data.observation_queries:
        if query.case_id != case_id:
            continue
        if query.time_s not in history:
            continue
        surface_temperature_k = float(history[query.time_s][0])
        samples = data.radiometer_bands[query.band_id]
        radiance = band_radiance(
            samples,
            surface_temperature_k,
            surface_material.surface_emissivity,
            data.config,
        )
        brightness = brightness_temperature(
            samples,
            radiance,
            data.config,
        )
        rows.append(
            {
                "observation_id": query.observation_id,
                "case_id": case_id,
                "time_s": query.time_s,
                "band_id": query.band_id,
                "surface_temperature_k": surface_temperature_k,
                "band_radiance_w_m2_sr": radiance,
                "brightness_temperature_k": brightness,
            }
        )
    rows.sort(key=lambda row: (row["observation_id"],))
    return rows


def inversion_objective(
    model: ThermalModel,
    data: SolverData,
    fit: InversionFit,
    parameters: Sequence[float],
) -> Tuple[float, Dict[str, float]]:
    param_map = dict(zip(fit.parameter_names, parameters))
    case_result = model.run_forward_case(
        fit.case_id,
        conductivity_scale=param_map.get("conductivity_scale"),
        albedo_offset=param_map.get("albedo_offset"),
    )
    radiometer_rows = {
        row["observation_id"]: row for row in build_radiometer_rows(data, case_result)
    }
    objective = 0.0
    predictions: Dict[str, float] = {}
    for obs_id, target, weight in zip(
        fit.observation_ids,
        fit.target_brightness_temperatures_k,
        fit.observation_weights,
    ):
        predicted = radiometer_rows[obs_id]["brightness_temperature_k"]
        predictions[obs_id] = predicted
        delta = predicted - target
        objective += weight * delta * delta
    return objective, predictions


def solve_one_parameter_inversion(
    model: ThermalModel,
    data: SolverData,
    fit: InversionFit,
) -> Dict[str, Any]:
    config = data.config
    lower = fit.lower_bounds[0]
    upper = fit.upper_bounds[0]
    evaluations = 0

    def objective_at(value: float) -> float:
        nonlocal evaluations
        evaluations += 1
        if evaluations > config.inversion_max_evaluations:
            raise RuntimeError(f"inversion exceeded evaluation budget for {fit.fit_id}")
        objective, _ = inversion_objective(model, data, fit, (value,))
        return objective

    left = lower
    right = upper
    phi = 0.5 * (math.sqrt(5.0) - 1.0)
    x1 = right - phi * (right - left)
    x2 = left + phi * (right - left)
    f1 = objective_at(x1)
    f2 = objective_at(x2)
    best_value = x1 if f1 <= f2 else x2
    best_objective = min(f1, f2)

    tolerance = max(
        config.inversion_parameter_tolerance,
        (upper - lower) * config.inversion_parameter_tolerance,
    )
    while right - left > tolerance:
        if f1 <= f2:
            right = x2
            x2 = x1
            f2 = f1
            x1 = right - phi * (right - left)
            f1 = objective_at(x1)
            if f1 < best_objective:
                best_objective = f1
                best_value = x1
        else:
            left = x1
            x1 = x2
            f1 = f2
            x2 = left + phi * (right - left)
            f2 = objective_at(x2)
            if f2 < best_objective:
                best_objective = f2
                best_value = x2

    at_lower = abs(best_value - lower) <= tolerance
    at_upper = abs(best_value - upper) <= tolerance
    converged = best_objective <= config.inversion_objective_tolerance or (
        right - left <= tolerance
    )
    return {
        "fit_id": fit.fit_id,
        "case_id": fit.case_id,
        "parameter_names": list(fit.parameter_names),
        "parameter_values": [best_value],
        "objective": best_objective,
        "evaluation_count": evaluations,
        "converged": converged,
        "at_parameter_bound": at_lower or at_upper,
    }


def solve_two_parameter_inversion(
    model: ThermalModel,
    data: SolverData,
    fit: InversionFit,
) -> Dict[str, Any]:
    config = data.config
    evaluations = 0
    lower_bounds = list(fit.lower_bounds)
    upper_bounds = list(fit.upper_bounds)
    best = list(fit.initial_values)
    best_objective = float("inf")

    def evaluate(candidate: Sequence[float]) -> float:
        nonlocal evaluations, best, best_objective
        evaluations += 1
        if evaluations > config.inversion_max_evaluations:
            raise RuntimeError(f"inversion exceeded evaluation budget for {fit.fit_id}")
        objective, _ = inversion_objective(model, data, fit, candidate)
        if objective < best_objective:
            best = list(candidate)
            best_objective = objective
        return objective

    # Coarse grid then coordinate golden-section refinement.
    grid_size = 9
    for index_a in range(grid_size):
        fraction_a = index_a / (grid_size - 1)
        value_a = lower_bounds[0] + fraction_a * (upper_bounds[0] - lower_bounds[0])
        for index_b in range(grid_size):
            fraction_b = index_b / (grid_size - 1)
            value_b = lower_bounds[1] + fraction_b * (upper_bounds[1] - lower_bounds[1])
            evaluate([value_a, value_b])

    phi = 0.5 * (math.sqrt(5.0) - 1.0)
    for _pass in range(4):
        for index in range(2):
            left = lower_bounds[index]
            right = upper_bounds[index]
            x1 = right - phi * (right - left)
            x2 = left + phi * (right - left)

            def obj_at(value: float, fixed_index: int = index) -> float:
                candidate = best.copy()
                candidate[fixed_index] = value
                return evaluate(candidate)

            f1 = obj_at(x1)
            f2 = obj_at(x2)
            tolerance = max(
                config.inversion_parameter_tolerance,
                (upper_bounds[index] - lower_bounds[index]) * config.inversion_parameter_tolerance,
            )
            while right - left > tolerance and evaluations < config.inversion_max_evaluations:
                if f1 <= f2:
                    right = x2
                    x2 = x1
                    f2 = f1
                    x1 = right - phi * (right - left)
                    f1 = obj_at(x1)
                else:
                    left = x1
                    x1 = x2
                    f1 = f2
                    x2 = left + phi * (right - left)
                    f2 = obj_at(x2)

    at_bound = any(
        abs(best[index] - lower_bounds[index]) <= config.inversion_parameter_tolerance
        or abs(best[index] - upper_bounds[index]) <= config.inversion_parameter_tolerance
        for index in range(2)
    )
    converged = best_objective <= config.inversion_objective_tolerance
    return {
        "fit_id": fit.fit_id,
        "case_id": fit.case_id,
        "parameter_names": list(fit.parameter_names),
        "parameter_values": best,
        "objective": best_objective,
        "evaluation_count": evaluations,
        "converged": converged,
        "at_parameter_bound": at_bound,
    }


def solve_inversion_fit(model: ThermalModel, data: SolverData, fit: InversionFit) -> Dict[str, Any]:
    if len(fit.parameter_names) == 1:
        return solve_one_parameter_inversion(model, data, fit)
    if len(fit.parameter_names) == 2:
        return solve_two_parameter_inversion(model, data, fit)
    raise ValueError(f"unsupported inversion parameter count for {fit.fit_id}")


def round_output_value(value: Any, decimal_places: int) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, decimal_places)
    if isinstance(value, list):
        return [round_output_value(item, decimal_places) for item in value]
    if isinstance(value, dict):
        return {
            key: round_output_value(item, decimal_places)
            for key, item in value.items()
        }
    return value


def canonical_observation_count(data: SolverData) -> int:
    return len(data.observation_queries)


def build_report(data_dir: Path | str) -> Dict[str, Any]:
    data = load_solver_data(data_dir)
    model = ThermalModel(data)
    decimal_places = data.config.output_decimal_places

    time_step_rows: List[Dict[str, Any]] = []
    temperature_rows: List[Dict[str, Any]] = []
    surface_flux_rows: List[Dict[str, Any]] = []
    radiometer_rows: List[Dict[str, Any]] = []
    solver_diagnostics: List[Dict[str, Any]] = []

    case_ids = sorted(data.illumination_cases.keys())
    for case_id in case_ids:
        case_result = model.run_forward_case(case_id)
        time_step_rows.extend(case_result["time_step_rows"])
        surface_flux_rows.extend(case_result["surface_flux_rows"])
        temperature_rows.extend(build_temperature_rows(data, case_result))
        radiometer_rows.extend(build_radiometer_rows(data, case_result))

        max_step_residual = max(
            row["maximum_residual_w_m2"] for row in case_result["time_step_rows"]
        )
        all_temperatures = [
            float(value)
            for history in case_result["temperature_history"].values()
            for value in history
        ]
        solver_diagnostics.append(
            {
                "case_id": case_id,
                "spinup_cycles": case_result["spinup_cycles"],
                "final_spinup_difference_k": case_result["final_spinup_difference_k"],
                "report_step_count": len(case_result["time_step_rows"]),
                "maximum_step_residual_w_m2": max_step_residual,
                "minimum_temperature_k": min(all_temperatures),
                "maximum_temperature_k": max(all_temperatures),
                "all_values_finite": all(math.isfinite(value) for value in all_temperatures),
            }
        )

    time_step_rows.sort(key=lambda row: (row["case_id"], row["step_index"]))
    surface_flux_rows.sort(key=lambda row: (row["case_id"], row["step_index"]))
    temperature_rows.sort(
        key=lambda row: (row["case_id"], row["observation_id"], row["cell_index"])
    )
    radiometer_rows.sort(key=lambda row: (row["observation_id"],))
    solver_diagnostics.sort(key=lambda row: (row["case_id"],))

    inverse_fit_rows: List[Dict[str, Any]] = []
    for fit in sorted(data.inversion_fits, key=lambda item: item.fit_id):
        inverse_fit_rows.append(solve_inversion_fit(model, data, fit))
    inverse_fit_rows.sort(key=lambda row: (row["fit_id"],))

    converged_inverse_fit_count = sum(
        1 for row in inverse_fit_rows if row["converged"]
    )
    surface_temperature_values = [
        row["surface_temperature_k"] for row in radiometer_rows
    ]
    brightness_values = [row["brightness_temperature_k"] for row in radiometer_rows]
    energy_residuals = [
        abs(row["energy_residual_j_m2"]) for row in surface_flux_rows
    ]
    objectives = [row["objective"] for row in inverse_fit_rows]

    summary = {
        "case_count": len(case_ids),
        "observation_count": canonical_observation_count(data),
        "radiometer_row_count": len(radiometer_rows),
        "inverse_fit_count": len(inverse_fit_rows),
        "converged_inverse_fit_count": converged_inverse_fit_count,
        "minimum_surface_temperature_k": min(surface_temperature_values)
        if surface_temperature_values
        else 0.0,
        "maximum_surface_temperature_k": max(surface_temperature_values)
        if surface_temperature_values
        else 0.0,
        "maximum_brightness_temperature_k": max(brightness_values)
        if brightness_values
        else 0.0,
        "minimum_inversion_objective": min(objectives) if objectives else 0.0,
        "maximum_absolute_energy_residual_j_m2": max(energy_residuals)
        if energy_residuals
        else 0.0,
    }

    report = {
        "time_step_rows": time_step_rows,
        "temperature_rows": temperature_rows,
        "surface_flux_rows": surface_flux_rows,
        "radiometer_rows": radiometer_rows,
        "inverse_fit_rows": inverse_fit_rows,
        "solver_diagnostics": solver_diagnostics,
        "summary": summary,
    }
    return round_output_value(report, decimal_places)


def compute_brightness_targets(
    data_dir: Path | str,
    case_id: str,
    conductivity_scale: float,
    albedo_offset: float,
    observation_ids: Sequence[str],
) -> List[float]:
    data = load_solver_data(data_dir)
    model = ThermalModel(data)
    case_result = model.run_forward_case(
        case_id,
        conductivity_scale=conductivity_scale,
        albedo_offset=albedo_offset,
    )
    radiometer_rows = {
        row["observation_id"]: row for row in build_radiometer_rows(data, case_result)
    }
    return [radiometer_rows[obs_id]["brightness_temperature_k"] for obs_id in observation_ids]


def solve(data_dir: Path | str) -> Dict[str, Any]:
    return build_report(data_dir)
