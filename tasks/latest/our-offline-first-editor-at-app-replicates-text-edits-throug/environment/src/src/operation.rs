use std::collections::HashMap;
use std::fmt;

use serde::{Deserialize, Serialize};

use crate::vector_clock::VectorClock;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct OpId {
    pub replica: u32,
    pub counter: u64,
}

impl OpId {
    pub fn new(replica: u32, counter: u64) -> Self {
        Self { replica, counter }
    }
}

impl fmt::Display for OpId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}:{}", self.replica, self.counter)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Operation {
    Insert {
        after: Option<OpId>,
        id: OpId,
        value: char,
    },
    Delete {
        id: OpId,
    },
}

impl Operation {
    pub fn id(&self) -> OpId {
        match self {
            Operation::Insert { id, .. } => *id,
            Operation::Delete { id } => *id,
        }
    }

    pub fn canonical_bytes(&self) -> Vec<u8> {
        match self {
            Operation::Insert { after, id, value } => {
                let after = after.map(|a| a.to_string()).unwrap_or_else(|| "HEAD".to_string());
                format!("INS|{after}|{id}|{value}").into_bytes()
            }
            Operation::Delete { id } => format!("DEL|{id}").into_bytes(),
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct OpLog {
    entries: HashMap<OpId, (Operation, VectorClock)>,
}

impl OpLog {
    pub fn insert(&mut self, op: Operation, clock: VectorClock) {
        self.entries.insert(op.id(), (op, clock));
    }

    pub fn get(&self, id: &OpId) -> Option<&(Operation, VectorClock)> {
        self.entries.get(id)
    }

    pub fn sorted_ids(&self) -> Vec<OpId> {
        let mut ids: Vec<OpId> = self.entries.keys().copied().collect();
        ids.sort();
        ids
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}
