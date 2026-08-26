use std::collections::HashMap;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::operation::{OpId, Operation};
use crate::vector_clock::VectorClock;

pub const MERKLE_NOT_IMPLEMENTED: &str = "merkle dag not implemented";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MerkleError {
    InvalidPath(String),
}

impl std::fmt::Display for MerkleError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MerkleError::InvalidPath(path) => write!(f, "invalid merkle path: {path}"),
        }
    }
}

impl std::error::Error for MerkleError {}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MerkleExport {
    pub path: String,
    pub hash: [u8; 32],
    pub clock: VectorClock,
    pub op: Option<Operation>,
}

#[derive(Debug, Clone)]
struct TreeNode {
    hash: [u8; 32],
    clock: VectorClock,
    op: Option<Operation>,
}

#[derive(Debug, Clone, Default)]
pub struct MerkleDag {
    replica: u32,
    nodes: HashMap<String, TreeNode>,
    entries: HashMap<OpId, (Operation, VectorClock)>,
    root_hash: [u8; 32],
}

impl MerkleDag {
    pub fn new(replica: u32) -> Self {
        let mut dag = Self {
            replica,
            nodes: HashMap::new(),
            entries: HashMap::new(),
            root_hash: hash_bytes(b"MERKLE-CRDT-EMPTY"),
        };
        dag.rebuild();
        dag
    }

    pub fn ingest(&mut self, op: &Operation, clock: &VectorClock) -> Result<(), MerkleError> {
        self.entries.insert(op.id(), (op.clone(), clock.clone()));
        self.rebuild();
        Ok(())
    }

    pub fn root_hash(&self) -> [u8; 32] {
        self.root_hash
    }

    pub fn subtree_hash(&self, path: &str) -> Result<[u8; 32], MerkleError> {
        self.nodes
            .get(path)
            .map(|node| node.hash)
            .ok_or_else(|| MerkleError::InvalidPath(path.to_string()))
    }

    pub fn node_clock(&self, path: &str) -> Result<VectorClock, MerkleError> {
        self.nodes
            .get(path)
            .map(|node| node.clock.clone())
            .ok_or_else(|| MerkleError::InvalidPath(path.to_string()))
    }

    pub fn export_node(&self, path: &str) -> Result<MerkleExport, MerkleError> {
        let node = self
            .nodes
            .get(path)
            .ok_or_else(|| MerkleError::InvalidPath(path.to_string()))?;
        Ok(MerkleExport {
            path: path.to_string(),
            hash: node.hash,
            clock: node.clock.clone(),
            op: node.op.clone(),
        })
    }

    pub fn import_node(&mut self, export: MerkleExport) -> Result<(), MerkleError> {
        if let Some(op) = export.op.clone() {
            self.entries.insert(op.id(), (op, export.clock.clone()));
        }
        self.rebuild();
        Ok(())
    }

    pub fn diff_paths(&self, remote: &MerkleDag) -> Result<Vec<String>, MerkleError> {
        if self.root_hash == remote.root_hash {
            return Ok(Vec::new());
        }
        Ok(vec![String::new()])
    }

    pub fn replica_id(&self) -> u32 {
        self.replica
    }

    fn rebuild(&mut self) {
        self.nodes.clear();
        let ids: Vec<OpId> = {
            let mut keys: Vec<OpId> = self.entries.keys().copied().collect();
            keys.sort_by_key(|id| id.counter);
            keys
        };

        if ids.is_empty() {
            self.root_hash = hash_bytes(b"MERKLE-CRDT-EMPTY");
            self.nodes.insert(
                String::new(),
                TreeNode {
                    hash: self.root_hash,
                    clock: VectorClock::new(),
                    op: None,
                },
            );
            return;
        }

        self.root_hash = self.build_subtree("", &ids);
    }

    fn build_subtree(&mut self, path: &str, ids: &[OpId]) -> [u8; 32] {
        if ids.len() == 1 {
            let id = ids[0];
            let (op, clock) = self.entries.get(&id).cloned().unwrap();
            let mut payload = op.canonical_bytes();
            payload.extend_from_slice(&clock.canonical_bytes());
            let hash = hash_bytes(&payload);
            self.nodes.insert(
                path.to_string(),
                TreeNode {
                    hash,
                    clock,
                    op: Some(op),
                },
            );
            return hash;
        }

        let mid = ids.len() / 2;
        let (left_ids, right_ids) = ids.split_at(mid);
        let left_path = format!("{path}L");
        let right_path = format!("{path}R");
        let left_hash = self.build_subtree(&left_path, left_ids);
        let right_hash = self.build_subtree(&right_path, right_ids);

        let left_clock = self.nodes.get(&left_path).map(|n| &n.clock);
        let right_clock = self.nodes.get(&right_path).map(|n| &n.clock);
        let mut merged = VectorClock::new();
        if let Some(clock) = left_clock {
            merged.merge(clock);
        }
        if let Some(clock) = right_clock {
            merged.merge(clock);
        }

        let mut payload = Vec::with_capacity(64 + merged.canonical_bytes().len());
        payload.extend_from_slice(&left_hash);
        payload.extend_from_slice(&right_hash);
        payload.extend_from_slice(&merged.canonical_bytes());
        let hash = hash_bytes(&payload);
        self.nodes.insert(
            path.to_string(),
            TreeNode {
                hash,
                clock: merged,
                op: None,
            },
        );
        hash
    }
}

fn hash_bytes(data: &[u8]) -> [u8; 32] {
    Sha256::digest(data).into()
}
