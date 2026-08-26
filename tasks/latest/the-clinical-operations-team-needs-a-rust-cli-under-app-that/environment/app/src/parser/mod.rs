pub mod csv_reader;
pub mod event_merge;

use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct HospitalEvent {
    pub event_id: String,
    pub event_time: String,
    pub event_seq: u32,
    pub kind: EventKind,
}

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum EventKind {
    Admission {
        admission_id: String,
        patient_id: String,
        acuity_level: u8,
        preferred_ward: String,
    },
    Transfer {
        transfer_id: String,
        patient_id: String,
        from_ward: String,
        to_ward: String,
        status: String,
    },
    Procedure {
        procedure_id: String,
        patient_id: String,
        procedure_code: String,
        duration_minutes: u32,
        status: String,
    },
    Discharge {
        discharge_id: String,
        patient_id: String,
        disposition: String,
    },
}
