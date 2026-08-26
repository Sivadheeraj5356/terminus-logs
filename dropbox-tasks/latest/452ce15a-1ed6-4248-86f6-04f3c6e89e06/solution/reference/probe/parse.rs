use std::path::Path;

use std::collections::HashMap;

use crate::types::{ChipProfile, ChipReading, SegmentOverride};

pub fn parse_chip_text(path: &Path, raw: &str) -> Result<ChipProfile, String> {
    let mut family_id = String::new();
    let mut chip_id = String::new();
    let mut alias = String::new();
    let mut profile_id = String::new();
    let mut nominal_hz = 0.0_f64;
    let mut readings = Vec::new();
    let mut segment_overrides: HashMap<String, SegmentOverride> = HashMap::new();
    let mut in_readings = false;
    let mut segment_id = "default".to_string();

    for line in raw.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        let line = if let Some(idx) = trimmed.find('#') {
            trimmed[..idx].trim()
        } else {
            trimmed
        };
        if line.is_empty() {
            continue;
        }
        if let Some(rest) = line.strip_prefix("family_id=") {
            family_id = rest.trim().to_string();
            in_readings = false;
            continue;
        }
        if let Some(rest) = line.strip_prefix("chip_id=") {
            chip_id = rest.trim().to_string();
            in_readings = false;
            continue;
        }
        if let Some(rest) = line.strip_prefix("alias=") {
            alias = rest.trim().to_string();
            in_readings = false;
            continue;
        }
        if let Some(rest) = line.strip_prefix("profile_id=") {
            profile_id = rest.trim().to_string();
            in_readings = false;
            continue;
        }
        if let Some(rest) = line.strip_prefix("nominal_hz=") {
            nominal_hz = rest
                .trim()
                .parse()
                .map_err(|_| format!("{}: bad nominal_hz", path.display()))?;
            in_readings = false;
            continue;
        }
        if line == "readings:" {
            in_readings = true;
            segment_id = "default".to_string();
            continue;
        }
        if let Some(rest) = line.strip_prefix("segment:") {
            segment_id = rest.trim().to_string();
            if segment_id.is_empty() {
                return Err(format!("{}: empty segment id", path.display()));
            }
            segment_overrides
                .entry(segment_id.clone())
                .or_insert(SegmentOverride {
                    alpha_override: 0.0,
                    nominal_hz_override: 0.0,
                });
            continue;
        }
        if in_readings {
            if let Some(rest) = line.strip_prefix("alpha_override=") {
                let val: f64 = rest
                    .trim()
                    .parse()
                    .map_err(|_| format!("{}: bad alpha_override", path.display()))?;
                segment_overrides
                    .entry(segment_id.clone())
                    .or_insert(SegmentOverride {
                        alpha_override: 0.0,
                        nominal_hz_override: 0.0,
                    })
                    .alpha_override = val;
                continue;
            }
            if let Some(rest) = line.strip_prefix("nominal_hz_override=") {
                let val: f64 = rest
                    .trim()
                    .parse()
                    .map_err(|_| format!("{}: bad nominal_hz_override", path.display()))?;
                segment_overrides
                    .entry(segment_id.clone())
                    .or_insert(SegmentOverride {
                        alpha_override: 0.0,
                        nominal_hz_override: 0.0,
                    })
                    .nominal_hz_override = val;
                continue;
            }
            let mut parts = line.split_whitespace();
            let line_index = parts
                .next()
                .ok_or_else(|| format!("{}: bad reading row", path.display()))?
                .parse::<u32>()
                .map_err(|_| format!("{}: bad line_index", path.display()))?;
            let temp_c = parts
                .next()
                .ok_or_else(|| format!("{}: bad temp_c", path.display()))?
                .parse::<f64>()
                .map_err(|_| format!("{}: bad temp_c", path.display()))?;
            let freq_hz = parts
                .next()
                .ok_or_else(|| format!("{}: bad freq_hz", path.display()))?
                .parse::<f64>()
                .map_err(|_| format!("{}: bad freq_hz", path.display()))?;
            readings.push(ChipReading {
                line_index,
                segment_id: segment_id.clone(),
                temp_c,
                freq_hz,
            });
        }
    }

    if family_id.is_empty()
        || chip_id.is_empty()
        || profile_id.is_empty()
        || nominal_hz <= 0.0
        || readings.is_empty()
    {
        return Err(format!("{}: invalid chip file", path.display()));
    }

    Ok(ChipProfile {
        family_id,
        chip_id,
        alias,
        profile_id,
        nominal_hz,
        readings,
        segment_overrides,
    })
}
