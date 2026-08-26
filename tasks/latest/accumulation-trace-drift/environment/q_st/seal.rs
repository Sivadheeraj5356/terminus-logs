use crate::q_rd::{AccBuf, StepPhase};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SealMark {
    pub last_tag: u64,
    pub last_step: u32,
    pub pending_count: usize,
    #[serde(default)]
    pub wave_offset: u32,
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

    pub fn tags_path(&self) -> PathBuf {
        self.root.join("tags.bin")
    }
}

/// Persists accumulator snapshot bytes for a training phase.
pub fn seal_v(
    store: &Store,
    phase: StepPhase,
    buf: &AccBuf,
    last_step: u32,
    wave_offset: u32,
) -> SealMark {
    let last_tag = buf.tags.last().copied().unwrap_or(0);
    let pending_count = if phase == StepPhase::Folding {
        buf.tags.len()
    } else {
        0
    };
    let mark = SealMark {
        last_tag,
        last_step,
        pending_count,
        wave_offset,
    };
    fs::create_dir_all(&store.root).ok();
    let body = serde_json::to_string(&mark).unwrap_or_default();
    fs::write(store.manifest_path(), body).ok();
    if phase == StepPhase::StepReady {
        let snap = store.root.join("acc.bin");
        let bytes: Vec<u8> = buf.acc.iter().flat_map(|v| v.to_le_bytes()).collect();
        fs::write(snap, bytes).ok();
    }
    mark
}

pub fn write_manifest(store: &Store, mark: &SealMark) -> Result<(), String> {
    fs::create_dir_all(&store.root).map_err(|e| e.to_string())?;
    let body = serde_json::to_string(mark).map_err(|e| e.to_string())?;
    fs::write(store.manifest_path(), body).map_err(|e| e.to_string())
}

pub fn read_manifest(store: &Store) -> Result<SealMark, String> {
    let body = fs::read_to_string(store.manifest_path()).map_err(|e| e.to_string())?;
    serde_json::from_str(&body).map_err(|e| e.to_string())
}

pub fn read_tag_sidecar(store: &Store) -> Vec<u64> {
    let bytes = fs::read(store.tags_path()).unwrap_or_default();
    bytes
        .chunks_exact(8)
        .map(|chunk| u64::from_le_bytes(chunk.try_into().unwrap()))
        .collect()
}
