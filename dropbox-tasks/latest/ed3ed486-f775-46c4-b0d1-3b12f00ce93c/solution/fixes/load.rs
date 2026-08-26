use crate::q_rd::AccBuf;
use crate::q_st::{read_manifest, read_tag_sidecar, SealMark, Store};
use std::fs;

pub fn load_vault(store: &Store, window: usize) -> Result<(AccBuf, SealMark), String> {
    let mark = read_manifest(store)?;
    let mut buf = AccBuf::new(window.max(mark.pending_count.max(1)));
    if mark.pending_count > 0 {
        let snap = store.root.join("acc.bin");
        let bytes = fs::read(&snap).map_err(|e| e.to_string())?;
        let mut acc = Vec::new();
        for chunk in bytes.chunks_exact(4) {
            acc.push(f32::from_le_bytes(chunk.try_into().unwrap()));
        }
        buf.acc = acc;
        let tags = read_tag_sidecar(store);
        buf.tags = tags;
    }
    Ok((buf, mark))
}
