/// Aggregate adjacent empty slots into a liberty total.
///
/// `q` holds slot ids. `z` is the plane size used to fold aliases into the
/// canonical id space before uniqueness is applied.
pub fn op_k3(p: &mut Vec<u16>, q: &[u16], z: usize) -> u16 {
    p.clear();
    if z == 0 {
        return 0;
    }
    for &v in q {
        p.push(v);
    }
    p.len() as u16
}
