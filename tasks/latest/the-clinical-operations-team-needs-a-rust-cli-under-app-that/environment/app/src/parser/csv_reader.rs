use std::fs::File;
use std::path::Path;

use csv::ReaderBuilder;

use super::{EventKind, HospitalEvent};

pub fn load_all_events(input_dir: &Path) -> Result<Vec<HospitalEvent>, String> {
    let mut events = Vec::new();
    events.extend(load_admissions(&input_dir.join("admissions.csv"))?);
    events.extend(load_transfers(&input_dir.join("transfers.csv"))?);
    events.extend(load_procedures(&input_dir.join("procedures.csv"))?);
    events.extend(load_discharges(&input_dir.join("discharges.csv"))?);
    Ok(events)
}

fn read_csv<F>(path: &Path, mut map_row: F) -> Result<Vec<HospitalEvent>, String>
where
    F: FnMut(&csv::StringRecord, &csv::StringRecord) -> Result<HospitalEvent, String>,
{
    let file = File::open(path).map_err(|e| format!("open {}: {e}", path.display()))?;
    let mut reader = ReaderBuilder::new().trim(csv::Trim::All).from_reader(file);
    let headers = reader
        .headers()
        .map_err(|e| format!("headers {}: {e}", path.display()))?
        .clone();
    let mut out = Vec::new();
    for row in reader.records() {
        let row = row.map_err(|e| format!("read {}: {e}", path.display()))?;
        out.push(map_row(&row, &headers)?);
    }
    Ok(out)
}

fn load_admissions(path: &Path) -> Result<Vec<HospitalEvent>, String> {
    read_csv(path, |row, headers| {
        Ok(HospitalEvent {
            event_id: field(row, headers, "event_id")?,
            event_time: field(row, headers, "event_time")?,
            event_seq: parse_u32(field(row, headers, "event_seq")?)?,
            kind: EventKind::Admission {
                admission_id: field(row, headers, "admission_id")?,
                patient_id: field(row, headers, "patient_id")?,
                acuity_level: parse_u8(field(row, headers, "acuity_level")?)?,
                preferred_ward: field(row, headers, "preferred_ward")?,
            },
        })
    })
}

fn load_transfers(path: &Path) -> Result<Vec<HospitalEvent>, String> {
    read_csv(path, |row, headers| {
        Ok(HospitalEvent {
            event_id: field(row, headers, "event_id")?,
            event_time: field(row, headers, "event_time")?,
            event_seq: parse_u32(field(row, headers, "event_seq")?)?,
            kind: EventKind::Transfer {
                transfer_id: field(row, headers, "transfer_id")?,
                patient_id: field(row, headers, "patient_id")?,
                from_ward: field(row, headers, "from_ward")?,
                to_ward: field(row, headers, "to_ward")?,
                status: field(row, headers, "status")?,
            },
        })
    })
}

fn load_procedures(path: &Path) -> Result<Vec<HospitalEvent>, String> {
    read_csv(path, |row, headers| {
        Ok(HospitalEvent {
            event_id: field(row, headers, "event_id")?,
            event_time: field(row, headers, "event_time")?,
            event_seq: parse_u32(field(row, headers, "event_seq")?)?,
            kind: EventKind::Procedure {
                procedure_id: field(row, headers, "procedure_id")?,
                patient_id: field(row, headers, "patient_id")?,
                procedure_code: field(row, headers, "procedure_code")?,
                duration_minutes: parse_u32(field(row, headers, "duration_minutes")?)?,
                status: field(row, headers, "status")?,
            },
        })
    })
}

fn load_discharges(path: &Path) -> Result<Vec<HospitalEvent>, String> {
    read_csv(path, |row, headers| {
        Ok(HospitalEvent {
            event_id: field(row, headers, "event_id")?,
            event_time: field(row, headers, "event_time")?,
            event_seq: parse_u32(field(row, headers, "event_seq")?)?,
            kind: EventKind::Discharge {
                discharge_id: field(row, headers, "discharge_id")?,
                patient_id: field(row, headers, "patient_id")?,
                disposition: field(row, headers, "disposition")?,
            },
        })
    })
}

fn parse_u32(raw: String) -> Result<u32, String> {
    raw.parse().map_err(|e| format!("invalid u32 {raw}: {e}"))
}

fn parse_u8(raw: String) -> Result<u8, String> {
    raw.parse().map_err(|e| format!("invalid u8 {raw}: {e}"))
}

pub fn load_beds(input_dir: &Path) -> Result<Vec<(String, String, bool, bool)>, String> {
    read_simple_csv(&input_dir.join("beds.csv"), |row, headers| {
        Ok((
            field(row, headers, "bed_id")?,
            field(row, headers, "ward")?,
            field(row, headers, "is_icu")? == "true",
            field(row, headers, "status")? == "maintenance",
        ))
    })
}

pub fn load_capacity(input_dir: &Path) -> Result<Vec<(String, u32)>, String> {
    read_simple_csv(&input_dir.join("capacity.csv"), |row, headers| {
        Ok((field(row, headers, "ward")?, parse_u32(field(row, headers, "max_beds")?)?))
    })
}

fn read_simple_csv<F, T>(path: &Path, mut map_row: F) -> Result<Vec<T>, String>
where
    F: FnMut(&csv::StringRecord, &csv::StringRecord) -> Result<T, String>,
{
    let file = File::open(path).map_err(|e| format!("open {}: {e}", path.display()))?;
    let mut reader = ReaderBuilder::new().trim(csv::Trim::All).from_reader(file);
    let headers = reader
        .headers()
        .map_err(|e| format!("headers {}: {e}", path.display()))?
        .clone();
    let mut out = Vec::new();
    for row in reader.records() {
        let row = row.map_err(|e| format!("read {}: {e}", path.display()))?;
        out.push(map_row(&row, &headers)?);
    }
    Ok(out)
}

fn field(row: &csv::StringRecord, headers: &csv::StringRecord, name: &str) -> Result<String, String> {
    let idx = headers
        .iter()
        .position(|h| h == name)
        .ok_or_else(|| format!("missing column {name}"))?;
    row.get(idx)
        .map(|s| s.to_string())
        .ok_or_else(|| format!("missing value for {name}"))
}

pub fn load_as_of(input_dir: &Path) -> Result<String, String> {
    let path = input_dir.join("README.md");
    let text = std::fs::read_to_string(&path).map_err(|e| format!("read README: {e}"))?;
    for line in text.lines() {
        if let Some(rest) = line.strip_prefix("as_of:") {
            return Ok(rest.trim().to_string());
        }
    }
    Err("as_of not found in README.md".to_string())
}
