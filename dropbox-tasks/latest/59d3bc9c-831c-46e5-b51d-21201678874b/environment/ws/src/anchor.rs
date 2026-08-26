use vane::{GenPhase, Pool};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VaultMark {
    pub last_generation: u64,
    pub last_pass: u32,
    pub open_count: usize,
}

#[derive(Clone, Debug)]
pub struct Store {
    pub root: PathBuf,
}

impl Store {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    pub fn manifest_path(&self) -> PathBuf {
        self.root.join("manifest.json")
    }

    pub fn slot_path(&self) -> PathBuf {
        self.root.join("slots.bin")
    }

    pub fn pool_path(&self) -> PathBuf {
        self.root.join("pool.bin")
    }
}

/// Persists pool snapshot bytes for a runtime phase boundary.
pub fn mark_r(store: &Store, phase: GenPhase, pool: &Pool) -> VaultMark {
    let last_generation = pool.active_slots.last().copied().unwrap_or(0);
    let open_count = if phase == GenPhase::Drawing {
        pool.active_slots.len()
    } else {
        0
    };
    let mark = VaultMark {
        last_generation,
        last_pass: 0,
        open_count,
    };
    fs::create_dir_all(&store.root).ok();
    let body = serde_json::to_string(&mark).unwrap_or_default();
    fs::write(store.manifest_path(), body).ok();
    if phase == GenPhase::PassReady {
        let snap = store.pool_path();
        let bytes: Vec<u8> = pool.tape.iter().flat_map(|v| v.to_le_bytes()).collect();
        fs::write(snap, bytes).ok();
    }
    mark
}

pub fn write_manifest(store: &Store, mark: &VaultMark) -> Result<(), String> {
    fs::create_dir_all(&store.root).map_err(|e| e.to_string())?;
    let body = serde_json::to_string(mark).map_err(|e| e.to_string())?;
    fs::write(store.manifest_path(), body).map_err(|e| e.to_string())
}

pub fn read_manifest(store: &Store) -> Result<VaultMark, String> {
    let body = fs::read_to_string(store.manifest_path()).map_err(|e| e.to_string())?;
    serde_json::from_str(&body).map_err(|e| e.to_string())
}

pub fn read_slot_sidecar(store: &Store) -> Vec<u64> {
    let bytes = fs::read(store.slot_path()).unwrap_or_default();
    bytes
        .chunks_exact(8)
        .map(|chunk| u64::from_le_bytes(chunk.try_into().unwrap()))
        .collect()
}
