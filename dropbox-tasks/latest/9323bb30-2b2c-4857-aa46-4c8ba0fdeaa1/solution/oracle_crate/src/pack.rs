use anyhow::{bail, Context, Result};
use serde::Deserialize;
use std::fs;

#[derive(Debug, Deserialize)]
pub struct KvPack {
    pub seq_len: u32,
    pub indptr: Vec<u32>,
    pub indices: Vec<u32>,
    pub packed_mask_hex: String,
    pub heads: Vec<HeadPack>,
}

#[derive(Debug, Deserialize)]
pub struct HeadPack {
    pub scale: f32,
    pub zero_point: i8,
    pub tiles: Vec<Vec<i8>>,
}

pub fn load_pack(path: &str) -> Result<KvPack> {
    let raw = fs::read_to_string(path).with_context(|| format!("read pack {path}"))?;
    let pack: KvPack = serde_json::from_str(&raw)?;
    if pack.indptr.is_empty() || pack.indptr[0] != 0 {
        bail!("bad indptr");
    }
    let nnz = *pack.indptr.last().unwrap() as usize;
    if pack.indices.len() != nnz {
        bail!("indices/nnz mismatch");
    }
    Ok(pack)
}
