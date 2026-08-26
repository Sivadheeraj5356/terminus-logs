use manifest::{BookE, FrameD, ScoresF};

#[derive(Debug)]
pub struct EvalError(pub String);

impl std::fmt::Display for EvalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

pub fn scan_v(m: &FrameD, n: &BookE) -> Result<ScoresF, EvalError> {
    if m.parts.is_empty() || n.parts.is_empty() {
        return Err(EvalError("no partitions selected".into()));
    }
    Ok(ScoresF {
        score: m.state.score,
        ready: m.state.ready,
    })
}
