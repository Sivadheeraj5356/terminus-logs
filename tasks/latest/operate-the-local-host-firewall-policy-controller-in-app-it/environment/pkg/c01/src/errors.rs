use thiserror::Error;

#[derive(Debug, Error)]
pub enum PolicyError {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
    #[error("config: {0}")]
    Config(String),
    #[error("validation: {0}")]
    Validation(String),
    #[error("backend: {0}")]
    Backend(String),
    #[error("reconcile: {0}")]
    Reconcile(String),
    #[error("failpoint: {0}")]
    Failpoint(String),
}

pub type Result<T> = std::result::Result<T, PolicyError>;
