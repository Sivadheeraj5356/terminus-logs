pub fn decode_bits(hex_s: &str, nnz: usize) -> Vec<bool> {
    let bytes = hex::decode(hex_s).unwrap_or_default();
    let mut bits = Vec::with_capacity(nnz);
    for i in 0..nnz {
        let byte = bytes.get(i / 8).copied().unwrap_or(0);
        bits.push(((byte >> (i % 8)) & 1) == 1);
    }
    bits
}

pub fn expand_pairs(indptr: &[u32], indices: &[u32], bits: &[bool]) -> Vec<(u32, u32)> {
    let mut out = Vec::new();
    let n_q = indptr.len().saturating_sub(1);
    for qi in 0..n_q {
        let start = indptr[qi] as usize;
        let end = indptr[qi + 1] as usize;
        for (off, &kj) in indices[start..end].iter().enumerate() {
            let bit_idx = start + off;
            if bits.get(bit_idx).copied().unwrap_or(false) {
                out.push((qi as u32, kj));
            }
        }
    }
    out
}

pub fn count_ones(bits: &[bool]) -> u32 {
    bits.iter().filter(|b| **b).count() as u32
}

pub fn validate_indptr(indptr: &[u32], nnz: usize) -> bool {
    if indptr.is_empty() {
        return false;
    }
    indptr[0] == 0 && (*indptr.last().unwrap() as usize) == nnz
}
