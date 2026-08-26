use crate::errors::StreamError;
use crate::resource_table::ResourceTable;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CleanupMode {
    Leaky,
    WasiErrorCleanup,
}

impl CleanupMode {
    pub fn parse(raw: &str) -> Result<Self, String> {
        match raw {
            "leaky" => Ok(Self::Leaky),
            "wasi-error-cleanup" => Ok(Self::WasiErrorCleanup),
            other => Err(format!("unknown cleanup mode {other}")),
        }
    }

    pub fn as_report_mode(self) -> &'static str {
        match self {
            Self::Leaky => "leaky",
            Self::WasiErrorCleanup => "wasi-error-cleanup",
        }
    }
}

pub fn handle_wasi_error(table: &mut ResourceTable, error: &StreamError, mode: CleanupMode) {
    if mode == CleanupMode::WasiErrorCleanup {
        table.release_after_error(error.descriptor);
    }
}
