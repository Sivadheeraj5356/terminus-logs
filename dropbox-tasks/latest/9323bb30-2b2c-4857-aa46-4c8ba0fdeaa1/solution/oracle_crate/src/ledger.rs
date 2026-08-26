use anyhow::{bail, Context, Result};
use std::fs;
use std::io::{Read, Write};
use std::path::Path;

#[derive(Debug, Default, Clone)]
pub struct ResidencyLedger {
    pub run_epoch: u32,
    pub page_count: u32,
    pub map: Vec<(u32, u32)>,
    pub free_stack: Vec<u32>,
    pub m: Vec<f64>,
    pub ell: Vec<f64>,
    pub tiles_planned: u32,
    pub mask_bits: u32,
    /// Count of successful densifying compacts (persists across replan).
    pub compact_gen: u32,
    /// XOR custody of mask-kept schedule visits (set by plan; preserved by advance).
    pub visit_checksum: u32,
    /// Parent-chained tip folded on each advance (reset to 0 by plan).
    pub merkle_tip: u64,
    /// Residue ouroboros: seeded at plan; parent-chained on advance (residency-seal-schema).
    pub residue_u64: u64,
}

impl ResidencyLedger {
    pub fn pages_resident(&self) -> u32 {
        self.map.len() as u32
    }

    pub fn load(path: &str) -> Result<Self> {
        if !Path::new(path).exists() {
            return Ok(Self::default());
        }
        let mut f = fs::File::open(path).with_context(|| format!("open {path}"))?;
        let mut magic = [0u8; 4];
        f.read_exact(&mut magic)?;
        if &magic != b"KVT1" {
            bail!("bad magic");
        }
        let mut buf = [0u8; 4];
        let mut rd_u32 = |f: &mut fs::File| -> Result<u32> {
            f.read_exact(&mut buf)?;
            Ok(u32::from_le_bytes(buf))
        };
        let run_epoch = rd_u32(&mut f)?;
        let page_count = rd_u32(&mut f)?;
        let free_stack_len = rd_u32(&mut f)?;
        let n_map = rd_u32(&mut f)?;
        let mut map = Vec::with_capacity(n_map as usize);
        for _ in 0..n_map {
            let logical = rd_u32(&mut f)?;
            let physical = rd_u32(&mut f)?;
            map.push((logical, physical));
        }
        let mut free_stack = Vec::with_capacity(free_stack_len as usize);
        for _ in 0..free_stack_len {
            free_stack.push(rd_u32(&mut f)?);
        }
        let n_heads = rd_u32(&mut f)?;
        let mut m = Vec::with_capacity(n_heads as usize);
        let mut ell = Vec::with_capacity(n_heads as usize);
        let mut dbuf = [0u8; 8];
        for _ in 0..n_heads {
            f.read_exact(&mut dbuf)?;
            m.push(f64::from_le_bytes(dbuf));
            f.read_exact(&mut dbuf)?;
            ell.push(f64::from_le_bytes(dbuf));
        }
        let tiles_planned = rd_u32(&mut f).unwrap_or(0);
        let mask_bits = rd_u32(&mut f).unwrap_or(0);
        let compact_gen = rd_u32(&mut f).unwrap_or(0);
        let visit_checksum = rd_u32(&mut f).unwrap_or(0);
        let mut tip_buf = [0u8; 8];
        let merkle_tip = match f.read_exact(&mut tip_buf) {
            Ok(()) => u64::from_le_bytes(tip_buf),
            Err(_) => 0,
        };
        let mut res_buf = [0u8; 8];
        let residue_u64 = match f.read_exact(&mut res_buf) {
            Ok(()) => u64::from_le_bytes(res_buf),
            Err(_) => 0,
        };
        Ok(Self {
            run_epoch,
            page_count,
            map,
            free_stack,
            m,
            ell,
            tiles_planned,
            mask_bits,
            compact_gen,
            visit_checksum,
            merkle_tip,
            residue_u64,
        })
    }

    pub fn save(&self, path: &str) -> Result<()> {
        if let Some(parent) = Path::new(path).parent() {
            fs::create_dir_all(parent)?;
        }
        let mut f = fs::File::create(path).with_context(|| format!("create {path}"))?;
        f.write_all(b"KVT1")?;
        f.write_all(&self.run_epoch.to_le_bytes())?;
        f.write_all(&self.page_count.to_le_bytes())?;
        f.write_all(&(self.free_stack.len() as u32).to_le_bytes())?;
        f.write_all(&(self.map.len() as u32).to_le_bytes())?;
        for (logical, physical) in &self.map {
            f.write_all(&logical.to_le_bytes())?;
            f.write_all(&physical.to_le_bytes())?;
        }
        for p in &self.free_stack {
            f.write_all(&p.to_le_bytes())?;
        }
        f.write_all(&(self.m.len() as u32).to_le_bytes())?;
        for i in 0..self.m.len() {
            f.write_all(&self.m[i].to_le_bytes())?;
            f.write_all(&self.ell[i].to_le_bytes())?;
        }
        f.write_all(&self.tiles_planned.to_le_bytes())?;
        f.write_all(&self.mask_bits.to_le_bytes())?;
        f.write_all(&self.compact_gen.to_le_bytes())?;
        f.write_all(&self.visit_checksum.to_le_bytes())?;
        f.write_all(&self.merkle_tip.to_le_bytes())?;
        f.write_all(&self.residue_u64.to_le_bytes())?;
        Ok(())
    }
}
