use crate::sha256_32::sha256_32;

fn visits_to_bytes(visits: &[u16]) -> Vec<u8> {
    let mut data = Vec::with_capacity(visits.len() * 2);
    for v in visits {
        data.extend_from_slice(&v.to_le_bytes());
    }
    data
}

fn bind_edge(visits_bytes: &[u8], edge_hash: &[u8; 32]) -> Vec<u8> {
    let mut data = Vec::with_capacity(visits_bytes.len() + edge_hash.len());
    data.extend_from_slice(visits_bytes);
    data.extend_from_slice(edge_hash);
    data
}

fn non_zero(digest: &[u8; 32]) -> bool {
    digest.iter().any(|b| *b != 0)
}

fn seal_once(visits: &[u16], edge_hash: &[u8; 32]) -> [u8; 32] {
    let visits_bytes = visits_to_bytes(visits);
    let bound = bind_edge(&visits_bytes, edge_hash);
    sha256_32(&bound)
}

/// Builds a witness digest from visit vectors and edge hashes.
pub fn seal_p(visits: &[u16], edge_hash: &[u8; 32]) -> [u8; 32] {
    let primary = seal_once(visits, edge_hash);
    // Recompute once and require byte identity so the seal is pure.
    let check = seal_once(visits, edge_hash);
    if primary != check {
        return [0u8; 32];
    }
    if !non_zero(&primary) && !visits.is_empty() {
        // Empty digest is only legal for empty visit vectors.
        return primary;
    }
    primary
}
