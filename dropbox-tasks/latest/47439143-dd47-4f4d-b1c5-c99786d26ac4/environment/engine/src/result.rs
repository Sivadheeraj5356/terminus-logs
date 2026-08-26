//! SAP evaluation results. Frozen evidence.

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SapResult {
    Pass,
    Fail,
    SoftFail,
    Neutral,
    None_,
    PermError,
}

impl SapResult {
    pub fn name(self) -> &'static str {
        match self {
            SapResult::Pass => "PASS",
            SapResult::Fail => "FAIL",
            SapResult::SoftFail => "SOFTFAIL",
            SapResult::Neutral => "NEUTRAL",
            SapResult::None_ => "NONE",
            SapResult::PermError => "PERMERROR",
        }
    }
}
