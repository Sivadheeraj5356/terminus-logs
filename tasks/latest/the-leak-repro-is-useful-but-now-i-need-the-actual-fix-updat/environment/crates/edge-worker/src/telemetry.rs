#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TelemetryRecord {
    pub sensor_id: u32,
    pub value: i32,
    pub flags: u8,
}

impl TelemetryRecord {
    pub fn new(sensor_id: u32, value: i32, flags: u8) -> Self {
        Self {
            sensor_id,
            value,
            flags,
        }
    }
}
