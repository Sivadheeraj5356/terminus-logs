#[derive(Clone, Debug)]
pub struct NodeH {
    pub ix: u16,
    pub score: i32,
    pub kids: Vec<NodeH>,
    pub side: bool,
}

/// Expands frontier nodes under a budget and returns ordered candidates.
pub fn expand_k(root: &NodeH, budget: u32) -> Vec<NodeH> {
    let mut out = vec![root.clone()];
    let mut cur = root.clone();
    let mut used = 1u32;
    while used < budget {
        let mut best: Option<NodeH> = None;
        let mut best_score = i32::MIN;
        for kid in &cur.kids {
            if kid.score > best_score {
                best_score = kid.score;
                best = Some(kid.clone());
            }
        }
        match best {
            Some(n) => {
                out.push(n.clone());
                cur = n;
                used += 1;
            }
            None => break,
        }
    }
    out
}
