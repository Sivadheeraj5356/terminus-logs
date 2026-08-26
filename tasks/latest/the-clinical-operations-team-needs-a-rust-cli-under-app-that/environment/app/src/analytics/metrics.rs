use crate::state::FacilityState;

pub fn build_summary(state: &FacilityState, as_of: &str) -> serde_json::Value {
    let active = state
        .patients
        .values()
        .filter(|p| p.in_facility_at(as_of))
        .count() as u32;

    let total_admissions = state.patients.len() as u32;
    let total_procedures: u32 = state.patients.values().map(|p| p.procedure_count).sum();
    let discharged: u32 = state.patients.values().filter(|p| p.discharged).count() as u32;

    serde_json::json!({
        "total_admissions": total_admissions,
        "active_patients": active,
        "discharged_patients": discharged,
        "total_procedures": total_procedures,
        "peak_occupancy": state.peak_occupancy,
        "rejected_event_count": state.rejected_events.len(),
    })
}

pub fn patient_rows(state: &FacilityState, as_of: &str) -> Vec<serde_json::Value> {
    let mut rows: Vec<_> = state.patients.values().collect();
    rows.sort_by(|a, b| a.patient_id.cmp(&b.patient_id));

    rows.into_iter()
        .map(|p| {
            let status = if p.in_facility_at(as_of) {
                "in_facility"
            } else {
                "discharged"
            };
            serde_json::json!({
                "patient_id": p.patient_id,
                "acuity_level": p.acuity_level,
                "current_ward": p.current_ward,
                "bed_id": p.bed_id,
                "status": status,
                "procedure_count": p.procedure_count,
                "procedure_minutes": p.procedure_minutes,
                "los_hours": compute_los_hours(p.admission_time.as_str(), p.discharge_time.as_deref(), as_of),
            })
        })
        .collect()
}

pub fn compute_los_hours(admission: &str, discharge: Option<&str>, as_of: &str) -> u32 {
    let end = discharge.unwrap_or(as_of);
    whole_hours_between(admission, end)
}

fn whole_hours_between(start: &str, end: &str) -> u32 {
    let start_secs = parse_ts(start);
    let end_secs = parse_ts(end);
    if end_secs <= start_secs {
        return 0;
    }
    ((end_secs - start_secs) / 3600) as u32
}

fn parse_ts(raw: &str) -> i64 {
    let trimmed = raw.trim_end_matches('Z');
    let (date, time) = trimmed.split_once('T').unwrap_or((trimmed, "00:00:00"));
    let mut parts = date.split('-');
    let _y: i64 = parts.next().unwrap_or("1970").parse().unwrap_or(1970);
    let m: i64 = parts.next().unwrap_or("01").parse().unwrap_or(1);
    let d: i64 = parts.next().unwrap_or("01").parse().unwrap_or(1);
    let mut tparts = time.split(':');
    let h: i64 = tparts.next().unwrap_or("0").parse().unwrap_or(0);
    let min: i64 = tparts.next().unwrap_or("0").parse().unwrap_or(0);
    let s: i64 = tparts.next().unwrap_or("0").parse().unwrap_or(0);
    (((_y * 372 + m * 31 + d) * 24 + h) * 60 + min) * 60 + s
}
