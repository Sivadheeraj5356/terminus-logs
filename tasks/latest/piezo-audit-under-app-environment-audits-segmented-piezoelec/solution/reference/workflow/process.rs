use crate::calib::apply::ResolvedInputs;
use crate::types::{ChipProfile, ReadingRow, ResolvedProfile};

pub struct CalibContext<'a> {
    pub profile: &'a ChipProfile,
    pub resolved: &'a ResolvedProfile,
}

pub fn rows_for_family(
    ctx: &CalibContext<'_>,
    input_fingerprint: &str,
    profile_graph_hash: &str,
    family_id: &str,
) -> Result<Vec<ReadingRow>, String> {
    if let Some(cached) = crate::cache::retain::try_load_family_rows(
        input_fingerprint,
        profile_graph_hash,
        family_id,
    ) {
        return Ok(cached);
    }
    let inputs = ResolvedInputs {
        profile: ctx.profile,
        resolved: ctx.resolved,
    };
    let mut rows = crate::calib::apply::apply_calibration(&inputs);
    crate::probe::sort::sort_rows(&mut rows);
    let _ = crate::cache::retain::store_family_rows(
        input_fingerprint,
        profile_graph_hash,
        family_id,
        &rows,
    );
    Ok(rows)
}
