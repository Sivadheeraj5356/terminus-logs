use crate::types::{ChipProfile, ProfileRevision, ReadingRow, ResolvedProfile, SegmentOverride};

pub fn round4(value: f64) -> f64 {
    (value * 10000.0).round() / 10000.0
}

pub struct ResolvedInputs<'a> {
    pub profile: &'a ChipProfile,
    pub resolved: &'a ResolvedProfile,
}

pub fn effective_nominal_header(profile: &ChipProfile, resolved: &ResolvedProfile) -> f64 {
    if resolved.resolved_nominal_override > 0.0 {
        resolved.resolved_nominal_override
    } else {
        profile.nominal_hz
    }
}

fn segment_override<'a>(
    profile: &'a ChipProfile,
    segment_id: &str,
) -> Option<&'a SegmentOverride> {
    profile.segment_overrides.get(segment_id)
}

pub fn effective_alpha(
    profile: &ChipProfile,
    resolved: &ResolvedProfile,
    segment_id: &str,
) -> f64 {
    if let Some(seg) = segment_override(profile, segment_id) {
        if seg.alpha_override > 0.0 {
            return seg.alpha_override;
        }
    }
    resolved.resolved_alpha
}

pub fn effective_nominal_for_reading(
    profile: &ChipProfile,
    resolved: &ResolvedProfile,
    segment_id: &str,
) -> f64 {
    if let Some(seg) = segment_override(profile, segment_id) {
        if seg.nominal_hz_override > 0.0 {
            return seg.nominal_hz_override;
        }
    }
    if resolved.resolved_nominal_override > 0.0 {
        resolved.resolved_nominal_override
    } else {
        profile.nominal_hz
    }
}

pub fn freq_at_25(freq_hz: f64, temp_c: f64, alpha: f64) -> f64 {
    round4(freq_hz / (1.0 + alpha * (temp_c - 25.0)))
}

pub fn ppm_pull(freq_25_hz: f64, nominal_hz: f64) -> f64 {
    if nominal_hz == 0.0 {
        return 0.0;
    }
    round4((freq_25_hz - nominal_hz) / nominal_hz * 1_000_000.0)
}

pub fn apply_calibration(inputs: &ResolvedInputs<'_>) -> Vec<ReadingRow> {
    inputs
        .profile
        .readings
        .iter()
        .map(|reading| {
            let alpha = effective_alpha(inputs.profile, inputs.resolved, &reading.segment_id);
            let nominal =
                effective_nominal_for_reading(inputs.profile, inputs.resolved, &reading.segment_id);
            let freq_25_hz = freq_at_25(reading.freq_hz, reading.temp_c, alpha);
            let ppm = ppm_pull(freq_25_hz, nominal);
            ReadingRow {
                line_index: reading.line_index,
                segment_id: reading.segment_id.clone(),
                temp_c: reading.temp_c,
                freq_hz: reading.freq_hz,
                freq_25_hz,
                ppm_pull: ppm,
            }
        })
        .collect()
}

pub fn effective_nominal(profile: &ChipProfile, revision: &ProfileRevision) -> f64 {
    if revision.nominal_hz_override > 0.0 {
        revision.nominal_hz_override
    } else {
        profile.nominal_hz
    }
}
