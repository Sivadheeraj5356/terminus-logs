use super::app_root;

pub const MAGIC: &[u8; 4] = b"KVT1";

pub fn path_default() -> String {
    app_root::join_str("data/residency.bin")
}

pub fn bump_epoch(epoch: u32) -> u32 {
    epoch.wrapping_add(1)
}

pub fn assert_magic(buf: &[u8]) -> bool {
    buf.len() >= 4 && &buf[0..4] == MAGIC
}

pub fn ouroboros_pages_match(scheduler_pages: &[u32], seal_pages: &[u32]) -> bool {
    let mut a = scheduler_pages.to_vec();
    let mut b = seal_pages.to_vec();
    a.sort_unstable();
    b.sort_unstable();
    a == b
}
