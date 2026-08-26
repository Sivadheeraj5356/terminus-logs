#[derive(Clone, Debug)]
pub struct ObsQ {
    pub ix: u16,
    pub zone: u16,
    pub weight: u16,
}

#[derive(Clone, Debug)]
pub struct EdgeR {
    pub from_zone: u16,
    pub to_ix: u16,
    pub w: u16,
}

fn max_index(trace: &[ObsQ], edges: &[EdgeR]) -> u16 {
    let mut max_ix = 0u16;
    for o in trace {
        if o.ix > max_ix {
            max_ix = o.ix;
        }
    }
    for e in edges {
        if e.to_ix > max_ix {
            max_ix = e.to_ix;
        }
    }
    max_ix
}

fn mark_active(trace: &[ObsQ], active: &mut [bool]) {
    for o in trace {
        let z = o.zone as usize;
        if z < active.len() {
            active[z] = true;
        }
    }
}

fn apply_trace(trace: &[ObsQ], v: &mut [u16]) {
    for o in trace {
        let i = o.ix as usize;
        if i < v.len() {
            v[i] = v[i].saturating_add(o.weight);
        }
    }
}

fn apply_edges(edges: &[EdgeR], active: &[bool], v: &mut [u16]) {
    for e in edges {
        let z = e.from_zone as usize;
        if z < active.len() && active[z] {
            let i = e.to_ix as usize;
            if i < v.len() {
                v[i] = v[i].saturating_add(e.w);
            }
        }
    }
}

/// Folds observation traces against edge tables into a visit vector.
pub fn fold_m(trace: &[ObsQ], edges: &[EdgeR]) -> Vec<u16> {
    let max_ix = max_index(trace, edges);
    let n = (max_ix as usize) + 1;
    let mut v = vec![0u16; n];
    let mut active = vec![false; 128];
    mark_active(trace, &mut active);
    apply_trace(trace, &mut v);
    apply_edges(edges, &active, &mut v);
    // Deterministic normalize: leave index-aligned counts unchanged.
    let mut out = vec![0u16; n];
    for (i, val) in v.into_iter().enumerate() {
        out[i] = val;
    }
    out
}
