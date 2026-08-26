use std::fs;
use std::path::{Path, PathBuf};

use sha2::{Digest, Sha256};

use crate::types::{ChipProfile, ProfileRevision, ResolvedProfile};

const PROFILE_DIR: &str = "/app/environment/fixtures/profiles";

pub fn hash_float_token(value: f64) -> String {
    if value == 0.0 {
        return "0".to_string();
    }
    let rendered = format!("{value:.17}");
    let trimmed = rendered.trim_end_matches('0').trim_end_matches('.');
    trimmed.to_string()
}

/// Decimal token for four-decimal-rounded digest fields (ppm_pull, temp_c).
pub fn digest_float_token(value: f64) -> String {
    if value == 0.0 {
        return "0".to_string();
    }
    let scaled = (value * 10000.0).round() as i64;
    let negative = scaled < 0;
    let abs = scaled.unsigned_abs();
    let whole = abs / 10000;
    let frac = abs % 10000;
    let mut out = String::new();
    if negative {
        out.push('-');
    }
    out.push_str(&whole.to_string());
    if frac != 0 {
        out.push('.');
        let frac_digits = format!("{frac:04}");
        out.push_str(frac_digits.trim_end_matches('0'));
    }
    out
}

pub fn load_catalog() -> Result<Vec<ProfileRevision>, String> {
    let mut revisions = Vec::new();
    let dir = Path::new(PROFILE_DIR);
    if !dir.is_dir() {
        return Err(format!("missing profile catalog: {PROFILE_DIR}"));
    }
    for entry in fs::read_dir(dir).map_err(|e| format!("profile dir: {e}"))? {
        let entry = entry.map_err(|e| format!("profile entry: {e}"))?;
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) != Some("prof") {
            continue;
        }
        revisions.push(parse_profile_file(&path)?);
    }
    if revisions.is_empty() {
        return Err("empty profile catalog".into());
    }
    Ok(revisions)
}

fn parse_profile_file(path: &Path) -> Result<ProfileRevision, String> {
    let raw = fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut profile_id = String::new();
    let mut effective_date = String::new();
    let mut inherits = String::new();
    let mut alpha = 0.0_f64;
    let mut nominal_hz_override = 0.0_f64;
    let mut deprecation_window_days = 0_u32;
    let mut alpha_raw = String::new();
    let mut nominal_hz_override_raw = String::new();
    for line in raw.lines() {
        let line = line.split('#').next().unwrap_or("").trim();
        if let Some(rest) = line.strip_prefix("profile_id=") {
            profile_id = rest.trim().to_string();
        } else if let Some(rest) = line.strip_prefix("effective_date=") {
            effective_date = rest.trim().to_string();
        } else if let Some(rest) = line.strip_prefix("inherits=") {
            inherits = rest.trim().to_string();
        } else if let Some(rest) = line.strip_prefix("alpha=") {
            alpha_raw = rest.trim().to_string();
            if !alpha_raw.is_empty() {
                alpha = alpha_raw
                    .parse()
                    .map_err(|_| format!("{}: bad alpha", path.display()))?;
            }
        } else if let Some(rest) = line.strip_prefix("nominal_hz_override=") {
            nominal_hz_override_raw = rest.trim().to_string();
            if !nominal_hz_override_raw.is_empty() {
                nominal_hz_override = nominal_hz_override_raw
                    .parse()
                    .map_err(|_| format!("{}: bad nominal_hz_override", path.display()))?;
            }
        } else if let Some(rest) = line.strip_prefix("deprecation_window_days=") {
            deprecation_window_days = rest
                .trim()
                .parse()
                .map_err(|_| format!("{}: bad deprecation_window_days", path.display()))?;
        }
    }
    if profile_id.is_empty() || effective_date.is_empty() {
        return Err(format!("{}: invalid profile file", path.display()));
    }
    Ok(ProfileRevision {
        profile_id,
        effective_date,
        inherits,
        alpha,
        nominal_hz_override,
        deprecation_window_days,
        alpha_raw,
        nominal_hz_override_raw,
    })
}

fn is_deprecated(
    revision: &ProfileRevision,
    catalog: &[ProfileRevision],
    as_of: &str,
) -> bool {
    for newer in catalog {
        if newer.profile_id != revision.profile_id {
            continue;
        }
        if newer.effective_date.as_str() <= revision.effective_date.as_str() {
            continue;
        }
        if newer.effective_date.as_str() > as_of {
            continue;
        }
        let window = newer.deprecation_window_days;
        if window == 0 {
            return true;
        }
        let deprecate_after = add_days(&newer.effective_date, window);
        if as_of > deprecate_after.as_str() {
            return true;
        }
    }
    false
}

fn is_leap(year: i32) -> bool {
    year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
}

fn days_in_month(year: i32, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => {
            if is_leap(year) {
                29
            } else {
                28
            }
        }
        _ => 30,
    }
}

fn add_days(date: &str, days: u32) -> String {
    let parts: Vec<&str> = date.split('-').collect();
    let mut y: i32 = parts[0].parse().unwrap_or(1970);
    let mut m: u32 = parts[1].parse().unwrap_or(1);
    let mut d: u32 = parts[2].parse().unwrap_or(1);
    let mut remaining = i64::from(days);
    while remaining > 0 {
        let dim = i64::from(days_in_month(y, m));
        let day_left = dim - i64::from(d);
        if remaining <= day_left {
            d += remaining as u32;
            remaining = 0;
        } else {
            remaining -= day_left + 1;
            d = 1;
            if m == 12 {
                m = 1;
                y += 1;
            } else {
                m += 1;
            }
        }
    }
    format!("{y:04}-{m:02}-{d:02}")
}

pub fn select_revision(
    catalog: &[ProfileRevision],
    profile_id: &str,
    as_of: &str,
) -> Result<ProfileRevision, String> {
    let mut best: Option<&ProfileRevision> = None;
    for revision in catalog {
        if revision.profile_id != profile_id {
            continue;
        }
        if revision.effective_date.as_str() > as_of {
            continue;
        }
        if is_deprecated(revision, catalog, as_of) {
            continue;
        }
        match best {
            None => best = Some(revision),
            Some(current) => {
                if revision.effective_date.as_str() > current.effective_date.as_str() {
                    best = Some(revision);
                }
            }
        }
    }
    best.cloned()
        .ok_or_else(|| format!("no profile revision for {profile_id} as of {as_of}"))
}

pub fn resolve_profile(
    catalog: &[ProfileRevision],
    revision: &ProfileRevision,
    as_of: &str,
    seen: &mut Vec<String>,
) -> Result<ResolvedProfile, String> {
    if seen.contains(&revision.profile_id) {
        return Err(format!("inheritance cycle at {}", revision.profile_id));
    }
    seen.push(revision.profile_id.clone());

    let mut resolved_alpha = revision.alpha;
    let mut resolved_nominal = revision.nominal_hz_override;
    let mut parent_effective_date = String::new();

    if !revision.inherits.is_empty() {
        let parent = select_revision(catalog, &revision.inherits, as_of)?;
        parent_effective_date = parent.effective_date.clone();
        let parent_resolved = resolve_profile(catalog, &parent, as_of, seen)?;
        if resolved_alpha <= 0.0 {
            resolved_alpha = parent_resolved.resolved_alpha;
        }
        if resolved_nominal <= 0.0 {
            resolved_nominal = parent_resolved.resolved_nominal_override;
        }
    }

    if resolved_alpha <= 0.0 {
        return Err(format!(
            "unresolved alpha for profile {}",
            revision.profile_id
        ));
    }

    Ok(ResolvedProfile {
        revision: revision.clone(),
        parent_effective_date,
        resolved_alpha,
        resolved_nominal_override: resolved_nominal,
    })
}

pub fn segment_ids_for_profile(profile: &ChipProfile) -> Vec<String> {
    let mut ids = Vec::new();
    for reading in &profile.readings {
        if !ids.iter().any(|id| id == &reading.segment_id) {
            ids.push(reading.segment_id.clone());
        }
    }
    ids
}

#[derive(Clone)]
pub struct SegmentOverrideRef {
    pub family_id: String,
    pub chip_id: String,
    pub segment_id: String,
    pub alpha_override: f64,
    pub nominal_hz_override: f64,
}

pub fn profile_graph_hash(
    revisions: &[ProfileRevision],
    segment_overrides: &[SegmentOverrideRef],
) -> String {
    let mut revs = revisions.to_vec();
    revs.sort_by(|a, b| {
        a.profile_id
            .cmp(&b.profile_id)
            .then_with(|| a.effective_date.cmp(&b.effective_date))
    });
    let mut segs = segment_overrides.to_vec();
    segs.sort_by(|a, b| {
        a.family_id
            .cmp(&b.family_id)
            .then_with(|| a.chip_id.cmp(&b.chip_id))
            .then_with(|| a.segment_id.cmp(&b.segment_id))
    });
    let mut hasher = Sha256::new();
    for revision in revs {
        let override_token = if revision.nominal_hz_override > 0.0 {
            hash_float_token(revision.nominal_hz_override)
        } else {
            "0".to_string()
        };
        let line = format!(
            "{}|{}|{}|{}|{}|{}\n",
            revision.profile_id,
            revision.effective_date,
            hash_float_token(revision.alpha),
            override_token,
            revision.inherits,
            revision.deprecation_window_days
        );
        hasher.update(line.as_bytes());
    }
    for seg in segs {
        let alpha = if seg.alpha_override > 0.0 {
            hash_float_token(seg.alpha_override)
        } else {
            "0".to_string()
        };
        let nominal = if seg.nominal_hz_override > 0.0 {
            hash_float_token(seg.nominal_hz_override)
        } else {
            "0".to_string()
        };
        let line = format!(
            "{}|{}|{}|{}|{}\n",
            seg.family_id, seg.chip_id, seg.segment_id, alpha, nominal
        );
        hasher.update(line.as_bytes());
    }
    format!("sha256:{}", hex::encode(hasher.finalize()))
}

pub fn catalog_path() -> PathBuf {
    PathBuf::from(PROFILE_DIR)
}

pub fn collect_lineage(
    catalog: &[ProfileRevision],
    resolved: &ResolvedProfile,
    as_of: &str,
) -> Result<Vec<ProfileRevision>, String> {
    let mut chain = vec![resolved.revision.clone()];
    if !resolved.revision.inherits.is_empty() {
        let parent = select_revision(catalog, &resolved.revision.inherits, as_of)?;
        let parent_resolved = resolve_profile(catalog, &parent, as_of, &mut Vec::new())?;
        let mut parent_chain = collect_lineage(catalog, &parent_resolved, as_of)?;
        chain.append(&mut parent_chain);
    }
    chain.sort_by(|a, b| {
        a.profile_id
            .cmp(&b.profile_id)
            .then_with(|| a.effective_date.cmp(&b.effective_date))
    });
    chain.dedup_by(|a, b| a.profile_id == b.profile_id && a.effective_date == b.effective_date);
    Ok(chain)
}
