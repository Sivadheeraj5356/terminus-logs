use std::collections::{BTreeMap, HashMap};

use crate::operation::{OpId, Operation};

pub const SEQUENCE_NOT_IMPLEMENTED: &str = "sequence crdt not implemented";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SequenceError {
    NotImplemented,
    DuplicateId(OpId),
    MissingReference(OpId),
}

impl std::fmt::Display for SequenceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SequenceError::NotImplemented => write!(f, "{SEQUENCE_NOT_IMPLEMENTED}"),
            SequenceError::DuplicateId(id) => write!(f, "duplicate operation id {id}"),
            SequenceError::MissingReference(id) => write!(f, "missing reference id {id}"),
        }
    }
}

impl std::error::Error for SequenceError {}

#[derive(Debug, Clone)]
struct RgaNode {
    after: Option<OpId>,
    value: char,
    deleted: bool,
}

#[derive(Debug, Clone, Default)]
pub struct SequenceState {
    nodes: HashMap<OpId, RgaNode>,
}

impl SequenceState {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn apply(&mut self, op: &Operation) -> Result<(), SequenceError> {
        match op {
            Operation::Insert { after, id, value } => {
                if self.nodes.contains_key(id) {
                    return Err(SequenceError::DuplicateId(*id));
                }
                if let Some(after_id) = after {
                    if !self.nodes.contains_key(after_id) {
                        return Err(SequenceError::MissingReference(*after_id));
                    }
                }
                self.nodes.insert(
                    *id,
                    RgaNode {
                        after: *after,
                        value: *value,
                        deleted: false,
                    },
                );
                Ok(())
            }
            Operation::Delete { id } => {
                if let Some(node) = self.nodes.get_mut(id) {
                    node.deleted = true;
                }
                Ok(())
            }
        }
    }

    pub fn materialize(&self) -> String {
        let mut children: BTreeMap<Option<OpId>, Vec<OpId>> = BTreeMap::new();
        for (id, node) in &self.nodes {
            children.entry(node.after).or_default().push(*id);
        }
        for ids in children.values_mut() {
            ids.sort_by_key(|id| id.counter);
        }

        let mut out = String::new();
        let mut stack = children.get(&None).cloned().unwrap_or_default();
        stack.reverse();
        while let Some(id) = stack.pop() {
            if let Some(node) = self.nodes.get(&id) {
                if !node.deleted {
                    out.push(node.value);
                }
                if let Some(kids) = children.get(&Some(id)) {
                    for child in kids.iter().rev() {
                        stack.push(*child);
                    }
                }
            }
        }
        out
    }

    pub fn visible_len(&self) -> usize {
        self.nodes.values().filter(|n| !n.deleted).count()
    }

    pub fn visible_op_ids(&self) -> Vec<OpId> {
        let mut ids: Vec<OpId> = self
            .nodes
            .iter()
            .filter(|(_, node)| !node.deleted)
            .map(|(id, _)| *id)
            .collect();
        ids.sort_by_key(|id| id.counter);
        ids
    }
}
