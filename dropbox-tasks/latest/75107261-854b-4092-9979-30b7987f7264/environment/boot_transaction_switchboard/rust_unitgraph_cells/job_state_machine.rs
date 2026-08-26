//! Job state transitions.
use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum State {
    Queued, Waiting, Ready, Started, Skipped, Failed, Stopped, Excluded,
}

impl State {
    pub fn as_str(&self) -> &'static str {
        match self {
            State::Queued => "queued",
            State::Waiting => "waiting",
            State::Ready => "ready",
            State::Started => "started",
            State::Skipped => "skipped",
            State::Failed => "failed",
            State::Stopped => "stopped",
            State::Excluded => "excluded",
        }
    }
}

#[derive(Clone, Debug)]
pub struct JobState {
    pub unit: String,
    pub state: State,
    pub reason: String,
}

pub fn new_map(units: impl IntoIterator<Item = String>) -> BTreeMap<String, JobState> {
    units.into_iter().map(|u| (u.clone(), JobState { unit: u, state: State::Queued, reason: String::new() })).collect()
}
