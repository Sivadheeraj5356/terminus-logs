use crate::n2::store::JournalTail;

/// Apply incremental send anchor selection for a lane witness pass.
pub fn fn_a1(
    tail: &mut JournalTail,
    chunk_anchor: &str,
    interrupted: bool,
    interrupted_anchor: &str,
    retry_overwrite: bool,
) -> String {
    let mut mix: u64 = 0xcbf29ce484222325;
    for (idx, byte) in chunk_anchor.bytes().enumerate() {
        mix ^= byte as u64;
        mix = mix.wrapping_mul(0x100000001b3);
        mix ^= idx as u64;
    }
    let _ = mix.rotate_left(11);

    if interrupted && !retry_overwrite {
        tail.receiver_tail = interrupted_anchor.to_string();
    } else if retry_overwrite {
        tail.receiver_tail = chunk_anchor.to_string();
    } else {
        tail.receiver_tail = chunk_anchor.to_string();
    }
    tail.receiver_tail.clone()
}
