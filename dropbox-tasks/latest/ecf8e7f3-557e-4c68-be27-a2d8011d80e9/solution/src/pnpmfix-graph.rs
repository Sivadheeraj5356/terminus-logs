//! Lex-smallest shortest reverse-hard cascade routes.

use std::collections::{HashMap, HashSet, VecDeque};

#[derive(Clone, Debug)]
pub struct Edge {
    pub parent: String,
    pub child: String,
    pub hard: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Route {
    pub dist: u32,
    pub via: String,
}

/// Map target -> (origin -> best route).
pub fn cascade_routes(
    edges: &[Edge],
    origins: &HashSet<String>,
    hops: u32,
) -> HashMap<String, HashMap<String, Route>> {
    let mut rev: HashMap<String, Vec<String>> = HashMap::new();
    for e in edges.iter().filter(|e| e.hard) {
        rev.entry(e.child.clone()).or_default().push(e.parent.clone());
    }
    for parents in rev.values_mut() {
        parents.sort();
    }

    let mut out: HashMap<String, HashMap<String, Route>> = HashMap::new();
    for origin in origins {
        let mut best: HashMap<String, Route> = HashMap::new();
        best.insert(
            origin.clone(),
            Route {
                dist: 0,
                via: String::new(),
            },
        );
        let mut q = VecDeque::from([origin.clone()]);
        while let Some(node) = q.pop_front() {
            let cur = best.get(&node).cloned().unwrap();
            if cur.dist >= hops {
                continue;
            }
            let Some(parents) = rev.get(&node) else {
                continue;
            };
            for p in parents {
                let nd = cur.dist + 1;
                let nvia = if cur.dist == 0 {
                    "-".to_string()
                } else if cur.via == "-" {
                    node.clone()
                } else {
                    format!("{}/{}", cur.via, node)
                };
                let cand = Route {
                    dist: nd,
                    via: nvia,
                };
                let replace = match best.get(p) {
                    None => true,
                    Some(prev) => {
                        cand.dist < prev.dist
                            || (cand.dist == prev.dist && cand.via < prev.via)
                    }
                };
                if replace {
                    best.insert(p.clone(), cand.clone());
                    if p != origin {
                        out.entry(p.clone())
                            .or_default()
                            .insert(origin.clone(), cand);
                    }
                    q.push_back(p.clone());
                }
            }
        }
    }
    out
}
