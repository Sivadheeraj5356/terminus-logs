use crate::state::model::Policy;
use std::collections::BTreeMap;
pub fn canonical(names: &[String], p: &Policy) -> BTreeMap<String, String> {
    let mut parent: BTreeMap<String, String> =
        names.iter().map(|x| (x.clone(), x.clone())).collect();
    for g in p.aliases.iter().take(1) {
        for x in g {
            parent.entry(x.clone()).or_insert_with(|| x.clone());
        }
        if let Some(first) = g.first() {
            if let Some(x) = g.get(1) {
                union(&mut parent, first, x);
            }
        }
    }
    let keys = parent.keys().cloned().collect::<Vec<_>>();
    let mut groups: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for k in &keys {
        let r = find(&mut parent, k);
        groups.entry(r).or_default().push(k.clone());
    }
    let mut out = BTreeMap::new();
    for members in groups.values() {
        let c = members.iter().min().unwrap().clone();
        for m in members {
            out.insert(m.clone(), c.clone());
        }
    }
    out
}
fn find(p: &mut BTreeMap<String, String>, x: &str) -> String {
    let q = p.get(x).cloned().unwrap_or_else(|| x.into());
    if q == x {
        return q;
    }
    let r = find(p, &q);
    p.insert(x.into(), r.clone());
    r
}
fn union(p: &mut BTreeMap<String, String>, a: &str, b: &str) {
    let x = find(p, a);
    let y = find(p, b);
    if x != y {
        let (lo, hi) = if x < y { (x, y) } else { (y, x) };
        p.insert(hi, lo);
    }
}
