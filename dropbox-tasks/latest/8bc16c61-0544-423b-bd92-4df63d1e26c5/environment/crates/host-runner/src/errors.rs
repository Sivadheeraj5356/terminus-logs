#[derive(Clone, Debug)]
pub struct StreamError {
    pub descriptor: u32,
    pub event: &'static str,
}

impl StreamError {
    pub fn transient_read_lag(descriptor: u32) -> Self {
        Self {
            descriptor,
            event: "transient-read-lag",
        }
    }
}
