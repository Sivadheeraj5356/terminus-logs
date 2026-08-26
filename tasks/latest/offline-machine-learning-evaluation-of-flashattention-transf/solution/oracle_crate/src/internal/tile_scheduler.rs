pub fn br_bc(br_cap: u32, bc_cap: u32, head_dim: u32) -> (u32, u32) {
    (br_cap.min(head_dim), bc_cap.min(head_dim))
}

pub fn visit_order(n_heads: u32, n_q: u32, n_k: u32) -> Vec<(u32, u32, u32)> {
    let mut out = Vec::new();
    for h in 0..n_heads {
        for qi in 0..n_q {
            for kj in 0..n_k {
                out.push((h, qi, kj));
            }
        }
    }
    out
}

pub fn logical_k(h: u32, kj: u32, n_k: u32) -> u32 {
    h * n_k + kj
}

pub fn tiles_planned_count(n_heads: u32, n_q: u32, n_k: u32) -> u32 {
    n_heads * n_q * n_k
}

pub fn mark_residency_request(logical: u32) -> u32 {
    logical
}
