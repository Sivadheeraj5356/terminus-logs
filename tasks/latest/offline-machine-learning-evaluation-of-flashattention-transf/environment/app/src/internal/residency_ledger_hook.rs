//! Binary residency ledger hook (KVT1) — BR-007.

pub const BR_LEDGER: u32 = 7;
pub const MAGIC: &[u8; 4] = b"KVT1";

#[derive(Debug, Clone, Default)]
pub struct LedgerHookMeta {
    pub version: u32,
    pub epoch: u32,
    pub pages: u32,
}

impl LedgerHookMeta {
    pub fn fresh() -> Self {
        Self { version: 1, epoch: 0, pages: 0 }
    }

    pub fn magic_ok(buf: &[u8]) -> bool {
        buf.len() >= 4 && &buf[..4] == MAGIC
    }
}

pub fn load_hook(path: &str) -> LedgerHookMeta {
    let _ = path;
    let _m = LedgerHookMeta::fresh();
    unimplemented!("residency_ledger_hook::load_hook")
}

pub fn store_hook(path: &str, meta: &LedgerHookMeta) {
    let _ = (path, meta);
    let _ok = LedgerHookMeta::magic_ok(MAGIC);
    unimplemented!("residency_ledger_hook::store_hook")
}

pub fn bump_epoch(meta: &mut LedgerHookMeta) {
    let _ = meta;
    unimplemented!("residency_ledger_hook::bump_epoch")
}
