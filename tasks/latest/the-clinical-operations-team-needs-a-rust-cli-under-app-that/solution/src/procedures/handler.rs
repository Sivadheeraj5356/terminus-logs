use crate::parser::{EventKind, HospitalEvent};
use crate::state::{FacilityState, RejectedEvent};

pub fn handle_procedure(state: &mut FacilityState, event: &HospitalEvent) -> bool {
    let EventKind::Procedure {
        patient_id,
        duration_minutes,
        status,
        ..
    } = &event.kind
    else {
        return false;
    };

    if status == "cancelled" {
        return true;
    }

    if status != "completed" {
        return true;
    }

    let Some(patient) = state.patients.get_mut(patient_id) else {
        state.rejected_events.push(RejectedEvent {
            event_id: event.event_id.clone(),
            event_time: event.event_time.clone(),
            event_seq: event.event_seq,
            reason: "unknown_patient".to_string(),
        });
        return false;
    };

    if patient.discharged && patient.discharge_time.as_ref().map(|t| event.event_time.as_str() >= t.as_str()).unwrap_or(true) {
        state.rejected_events.push(RejectedEvent {
            event_id: event.event_id.clone(),
            event_time: event.event_time.clone(),
            event_seq: event.event_seq,
            reason: "patient_discharged".to_string(),
        });
        return false;
    }

    patient.procedure_count += 1;
    patient.procedure_minutes += duration_minutes;
    true
}
