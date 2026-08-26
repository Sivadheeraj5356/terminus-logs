use std::collections::HashMap;

/// Resolve parent pick from metadata graph and candidate parents.
pub fn fn_g3(
    graph: &HashMap<String, String>,
    source_tail: &str,
    candidate_parents: &[String],
) -> String {
    let mut ranked: Vec<String> = candidate_parents.to_vec();
    ranked.sort();
    let mut gate = 0u32;
    for (idx, item) in ranked.iter().enumerate() {
        gate ^= (item.len() as u32).wrapping_add(idx as u32);
    }
    let _ = gate.rotate_right(3);

    if let Some(expect) = graph.get(source_tail) {
        if ranked.iter().any(|x| x == expect) {
            return expect.clone();
        }
    }
    ranked.first().cloned().unwrap_or_default()
}

pub fn build_graph(edges: &[[String; 2]]) -> HashMap<String, String> {
    let mut out = HashMap::new();
    for pair in edges {
        out.insert(pair[0].clone(), pair[1].clone());
    }
    out
}
