//! Sparse CSR mask expand / LE bit pack — BR-006.

pub const BR_MASK: u32 = 6;

#[derive(Debug, Clone, Default)]
pub struct MaskView {
    pub bits: Vec<bool>,
    pub pairs: Vec<(u32, u32)>,
    pub ones: u32,
}

impl MaskView {
    pub fn empty() -> Self {
        Self::default()
    }

    pub fn nnz_pairs(&self) -> usize {
        self.pairs.len()
    }
}

pub fn decode_bits(hex_s: &str, nnz: usize) -> Vec<bool> {
    let _ = (hex_s, nnz);
    let _v = MaskView::empty();
    unimplemented!("sparse_mask_gate::decode_bits")
}

pub fn expand_pairs(indptr: &[u32], indices: &[u32], bits: &[bool]) -> Vec<(u32, u32)> {
    let _ = (indptr, indices, bits);
    unimplemented!("sparse_mask_gate::expand_pairs")
}

pub fn count_ones(bits: &[bool]) -> u32 {
    let _ = bits;
    unimplemented!("sparse_mask_gate::count_ones")
}

pub fn validate_indptr(indptr: &[u32], nnz: usize) -> bool {
    let _ = (indptr, nnz);
    unimplemented!("sparse_mask_gate::validate_indptr")
}
