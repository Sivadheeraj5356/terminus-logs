use anyhow::Result;
use serde::Deserialize;

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

pub fn load_pack(_path: &str) -> Result<KvPack> {
    unimplemented!("load_pack")
}
