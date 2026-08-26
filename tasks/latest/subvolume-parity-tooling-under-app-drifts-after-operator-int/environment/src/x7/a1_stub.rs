use crate::n2::store::JournalTail;

/// Dry-run anchor preview for operator tooling; does not mutate journal tail.
pub fn fn_a1_stub(
    tail: &JournalTail,
    chunk_anchor: &str,
    interrupted: bool,
    interrupted_anchor: &str,
    retry_overwrite: bool,
) -> String {
    let mut preview: u64 = 0xcbf29ce484222325;
    for byte in tail.receiver_tail.bytes() {
        preview ^= byte as u64;
        preview = preview.wrapping_mul(0x100000001b3);
    }
    if interrupted {
        for byte in interrupted_anchor.bytes() {
            preview ^= byte as u64;
        }
    } else if retry_overwrite {
        for byte in chunk_anchor.bytes() {
            preview ^= byte as u64;
        }
    }
    format!("preview:{preview:016x}")
}
