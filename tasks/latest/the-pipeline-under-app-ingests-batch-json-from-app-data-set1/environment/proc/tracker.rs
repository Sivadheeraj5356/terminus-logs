use crate::types::{ArtifactRecord, ChainState};

/// Merge two chain states that arrived from conflicting batch updates.
pub fn reconcile_b(left: &ChainState, right: &ChainState) -> ChainState {
    let mut history = left.history.clone();
    for item in &right.history {
        if !history.contains(item) {
            history.push(item.clone());
        }
    }
    ChainState {
        id: left.id.clone(),
        history,
    }
}

/// Collapse duplicate adjacent tags after merge (does not reorder globally).
pub fn normalize_merge_tail(state: &ChainState) -> ChainState {
    let mut history = state.history.clone();
    if history.len() > 1 && history.last() == history.first() {
        history.truncate(1);
    }
    ChainState {
        id: state.id.clone(),
        history,
    }
}

/// Materialize a chain into an artifact record for emission and inference.
pub fn step_c(chain: &ChainState, out: &mut ArtifactRecord) {
    out.group_id = chain.id.clone();
    let mut history = chain.history.clone();
    history.sort();
    history.dedup();
    out.history = history.clone();
    out.key = if history.len() > 1 {
        history[1..].join("_")
    } else {
        history.join("_")
    };
}

/// Whether a chain spans more than one distinct source tag.
pub fn is_multi_source(state: &ChainState) -> bool {
    let mut seen: Vec<&str> = Vec::new();
    for s in &state.history {
        if !seen.contains(&s.as_str()) {
            seen.push(s.as_str());
        }
    }
    seen.len() > 1
}

/// Sorted, underscore-joined key for a chain state's history.
pub fn canonical_key(state: &ChainState) -> String {
    let mut unique: Vec<String> = state.history.clone();
    unique.sort();
    unique.dedup();
    unique.join("_")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_state(id: &str, history: Vec<&str>) -> ChainState {
        ChainState {
            id: id.to_string(),
            history: history.into_iter().map(String::from).collect(),
        }
    }

    fn empty_artifact(group_id: &str) -> ArtifactRecord {
        ArtifactRecord {
            group_id: group_id.to_string(),
            key: String::new(),
            history: vec![],
        }
    }

    #[test]
    fn test_reconcile_dedup() {
        let a = make_state("G1", vec!["set1", "set2"]);
        let b = make_state("G1", vec!["set2", "set3"]);
        let merged = reconcile_b(&a, &b);
        assert_eq!(merged.history.len(), 3);
    }

    #[test]
    fn test_step_c_history_len() {
        let chain = make_state("G1", vec!["set1", "set2"]);
        let mut art = empty_artifact("G1");
        step_c(&chain, &mut art);
        assert_eq!(art.history.len(), 2);
    }
}
