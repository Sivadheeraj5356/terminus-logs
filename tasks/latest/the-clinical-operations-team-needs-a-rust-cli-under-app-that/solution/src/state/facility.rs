use std::collections::{HashMap, HashSet};

use super::PatientRecord;

#[derive(Debug, Clone)]
pub struct BedInfo {
    pub bed_id: String,
    pub ward: String,
    pub is_icu: bool,
    pub maintenance: bool,
}

#[derive(Debug, Default)]
pub struct FacilityState {
    pub patients: HashMap<String, PatientRecord>,
    pub beds: HashMap<String, BedInfo>,
    pub ward_capacity: HashMap<String, u32>,
    pub bed_assignments: HashMap<String, String>,
    pub ward_occupancy: HashMap<String, u32>,
    pub seen_event_ids: HashSet<String>,
    pub peak_occupancy: u32,
    pub rejected_events: Vec<RejectedEvent>,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct RejectedEvent {
    pub event_id: String,
    pub event_time: String,
    pub event_seq: u32,
    pub reason: String,
}

impl FacilityState {
    pub fn occupancy(&self) -> u32 {
        self.bed_assignments.len() as u32
    }

    pub fn refresh_peak(&mut self) {
        let current = self.occupancy();
        if current > self.peak_occupancy {
            self.peak_occupancy = current;
        }
    }

    pub fn critical_in_facility(&self) -> u32 {
        self.patients
            .values()
            .filter(|p| !p.discharged && p.acuity_level == 1)
            .count() as u32
    }

    pub fn ward_at_capacity(&self, ward: &str) -> bool {
        let cap = self.ward_capacity.get(ward).copied().unwrap_or(0);
        let occ = self.ward_occupancy.get(ward).copied().unwrap_or(0);
        occ >= cap
    }

    pub fn available_beds_in_ward(&self, ward: &str, acuity: u8) -> Vec<String> {
        let mut beds: Vec<String> = self
            .beds
            .values()
            .filter(|b| {
                b.ward == ward
                    && !b.maintenance
                    && !self.bed_assignments.contains_key(&b.bed_id)
                    && icu_allowed(b.is_icu, acuity, self.critical_in_facility())
            })
            .map(|b| b.bed_id.clone())
            .collect();
        beds.sort();
        beds
    }

    pub fn icu_beds_available(&self) -> Vec<String> {
        self.beds
            .values()
            .filter(|b| {
                b.is_icu
                    && !b.maintenance
                    && !self.bed_assignments.contains_key(&b.bed_id)
            })
            .map(|b| b.bed_id.clone())
            .collect()
    }
}

fn icu_allowed(is_icu: bool, acuity: u8, critical_count: u32) -> bool {
    if !is_icu {
        return true;
    }
    if acuity == 1 {
        return true;
    }
    critical_count == 0
}
