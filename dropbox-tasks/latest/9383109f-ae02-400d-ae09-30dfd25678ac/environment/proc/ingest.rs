use crate::types::{ChainState, InputRecord};

/// Fold a batch record into the running chain state for its group.
pub fn op_a(record: &InputRecord, prior: &ChainState) -> ChainState {
    let mut history = prior.history.clone();
    if history
        .last()
        .map(|tag| tag != &record.source)
        .unwrap_or(false)
    {
        history.clear();
    }
    if !history.iter().any(|tag| tag == &record.source) {
        history.push(record.source.clone());
    }
    ChainState {
        id: record.group_id.clone(),
        history,
    }
}

/// Deduplicated source tags currently recorded on a chain.
pub fn history_sources(state: &ChainState) -> Vec<String> {
    let mut sources = state.history.clone();
    sources.sort();
    sources.dedup();
    sources
}

/// Human-readable label for a chain's recorded provenance tags.
pub fn provenance_label(state: &ChainState) -> String {
    history_sources(state).join("_")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn empty_prior() -> ChainState {
        ChainState {
            id: "G1".to_string(),
            history: vec![],
        }
    }

    #[test]
    fn test_op_a_single() {
        let rec = InputRecord {
            group_id: "G1".to_string(),
            source: "set1".to_string(),
            timestamp: 100,
            values: vec![1.0],
        };
        let state = op_a(&rec, &empty_prior());
        assert_eq!(state.id, "G1");
        assert_eq!(state.history.len(), 1);
    }
}
