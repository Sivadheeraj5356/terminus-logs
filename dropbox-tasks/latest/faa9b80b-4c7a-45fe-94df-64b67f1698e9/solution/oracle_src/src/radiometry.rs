//! Planck radiance, band integration and brightness-temperature inversion
//! for the simulated radiometer channels.

use crate::data::{BandSample, SolverConfig};
use crate::thermal::clamp;

pub fn planck_radiance(wavelength_m: f64, temperature_k: f64, config: &SolverConfig) -> f64 {
    if temperature_k <= 0.0 || wavelength_m <= 0.0 {
        return 0.0;
    }
    let h = config.planck_constant_j_s;
    let c = config.speed_of_light_m_s;
    let k_b = config.boltzmann_constant_j_k;
    let exponent = h * c / (wavelength_m * k_b * temperature_k);
    if exponent > 700.0 {
        return 0.0;
    }
    let denom = exponent.exp_m1();
    if denom <= 0.0 {
        return 0.0;
    }
    (2.0 * h * c * c) / (wavelength_m.powi(5) * denom)
}

fn response_reference(samples: &[BandSample]) -> f64 {
    samples
        .iter()
        .map(|sample| sample.response)
        .fold(0.0_f64, f64::max)
        .max(1.0e-300)
}

pub fn band_response_integral(samples: &[BandSample]) -> f64 {
    let reference = response_reference(samples);
    let mut total = 0.0;
    for index in 0..samples.len().saturating_sub(1) {
        let left = &samples[index];
        let right = &samples[index + 1];
        let delta_lambda_m = (right.wavelength_um - left.wavelength_um) * 1.0e-6;
        total += 0.5 * (left.response / reference + right.response / reference) * delta_lambda_m;
    }
    total * reference
}

fn normalized_band_terms(
    samples: &[BandSample],
    temperature_k: f64,
    config: &SolverConfig,
) -> (f64, f64) {
    let reference = response_reference(samples);
    let mut weighted = 0.0;
    let mut response = 0.0;
    for index in 0..samples.len().saturating_sub(1) {
        let left = &samples[index];
        let right = &samples[index + 1];
        let delta_lambda_m = (right.wavelength_um - left.wavelength_um) * 1.0e-6;
        let wavelength_left_m = left.wavelength_um * 1.0e-6;
        let wavelength_right_m = right.wavelength_um * 1.0e-6;
        let planck_left = planck_radiance(wavelength_left_m, temperature_k, config);
        let planck_right = planck_radiance(wavelength_right_m, temperature_k, config);
        let left_norm = left.response / reference;
        let right_norm = right.response / reference;
        weighted += 0.5 * (left_norm * planck_left + right_norm * planck_right) * delta_lambda_m;
        response += 0.5 * (left_norm + right_norm) * delta_lambda_m;
    }
    (weighted, response)
}

pub fn band_radiance(
    samples: &[BandSample],
    temperature_k: f64,
    emissivity: f64,
    config: &SolverConfig,
) -> f64 {
    let (weighted, response) = normalized_band_terms(samples, temperature_k, config);
    if response <= 0.0 {
        return 0.0;
    }
    emissivity * weighted / response
}

pub fn normalized_blackbody_integral(samples: &[BandSample], temperature_k: f64, config: &SolverConfig) -> f64 {
    let (weighted, response) = normalized_band_terms(samples, temperature_k, config);
    if response <= 0.0 {
        return 0.0;
    }
    weighted / response
}

pub fn brightness_temperature(samples: &[BandSample], observed_radiance: f64, config: &SolverConfig) -> f64 {
    if observed_radiance <= 0.0 {
        return config.minimum_temperature_k;
    }
    let target = observed_radiance;
    let mut low = config.minimum_temperature_k;
    let mut high = config.maximum_temperature_k;
    let mut f_low = normalized_blackbody_integral(samples, low, config) - target;
    let f_high = normalized_blackbody_integral(samples, high, config) - target;
    if f_low * f_high > 0.0 {
        return clamp(observed_radiance, low, high);
    }
    for _ in 0..config.brightness_temperature_max_iterations {
        let mid = 0.5 * (low + high);
        let f_mid = normalized_blackbody_integral(samples, mid, config) - target;
        if f_mid.abs() <= config.brightness_temperature_tolerance_k {
            return mid;
        }
        if f_low * f_mid <= 0.0 {
            high = mid;
        } else {
            low = mid;
            f_low = f_mid;
        }
    }
    0.5 * (low + high)
}
