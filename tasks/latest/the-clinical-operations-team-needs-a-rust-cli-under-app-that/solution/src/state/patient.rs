#[derive(Debug, Clone)]
pub struct PatientRecord {
    pub patient_id: String,
    pub acuity_level: u8,
    pub admission_time: String,
    pub current_ward: Option<String>,
    pub bed_id: Option<String>,
    pub discharged: bool,
    pub discharge_time: Option<String>,
    pub procedure_count: u32,
    pub procedure_minutes: u32,
}

impl PatientRecord {
    pub fn new(patient_id: String, acuity_level: u8, admission_time: String) -> Self {
        Self {
            patient_id,
            acuity_level,
            admission_time,
            current_ward: None,
            bed_id: None,
            discharged: false,
            discharge_time: None,
            procedure_count: 0,
            procedure_minutes: 0,
        }
    }

    pub fn in_facility_at(&self, as_of: &str) -> bool {
        if self.discharged {
            self.discharge_time
                .as_ref()
                .map(|t| as_of < t.as_str())
                .unwrap_or(false)
        } else {
            self.admission_time.as_str() <= as_of
        }
    }
}
