use crate::EV_CLEAR;

/// Reduce persisted event bytes into the digest progression.
///
/// Stream layout: repeating `kind_u8` + `digest_32`.
pub fn fold_v2(p: &mut Vec<[u8; 32]>, q: &[u8]) -> usize {
    let mut i = 0usize;
    while i + 33 <= q.len() {
        let kind = q[i];
        let mut dig = [0u8; 32];
        dig.copy_from_slice(&q[i + 1..i + 33]);
        if kind == EV_CLEAR {
            i += 33;
            continue;
        }
        p.push(dig);
        i += 33;
    }
    p.len()
}
