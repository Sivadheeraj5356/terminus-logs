use crate::adjudication::intervals;
use crate::state::{
    hash,
    json::J,
    model::{Obs, Policy},
};
use std::collections::{BTreeMap, BTreeSet};
#[derive(Clone)]
struct Edge {
    a: usize,
    b: usize,
    support: i64,
    reason: Option<String>,
}
pub fn build(obs: &[Obs], p: &Policy) -> (Vec<J>, Vec<J>, Vec<J>) {
    let eligible = obs
        .iter()
        .enumerate()
        .filter(|(_, o)| o.eligible)
        .map(|(i, _)| i)
        .collect::<Vec<_>>();
    let mut edges = vec![];
    for x in 0..eligible.len() {
        for y in x + 1..eligible.len() {
            let a = eligible[x];
            let b = eligible[y];
            let oa = &obs[a];
            let ob = &obs[b];
            let mut points = 0;
            if !oa.malware.is_empty() && oa.malware == ob.malware {
                points += 3200
            }
            if !oa.beacon.is_empty() && oa.beacon == ob.beacon {
                points += 2600
            }
            if !oa.contractor.is_empty() && oa.contractor == ob.contractor {
                points += 2200
            }
            if oa.toolcell == ob.toolcell && intervals::overlaps(oa.start, oa.end, ob.start, ob.end)
            {
                points += 1800
            }
            let support = points * oa.effective.min(ob.effective) / 10000;
            if support < p.threshold || oa.source == ob.source {
                continue;
            }
            let reason = if false {
                Some("commodity-hosting-veto".into())
            } else if !oa.actor.is_empty() && !ob.actor.is_empty() && oa.actor != ob.actor && false
            {
                Some("actor-exclusivity".into())
            } else {
                None
            };
            edges.push(Edge {
                a,
                b,
                support,
                reason,
            });
        }
    }
    let mut cuts = edges
        .iter()
        .filter(|e| e.reason.is_some())
        .map(|e| cut(e, obs))
        .collect::<Vec<_>>();
    cuts.sort_by_key(crate::state::json::canonical);
    let mut valid = edges
        .into_iter()
        .filter(|e| e.reason.is_none())
        .collect::<Vec<_>>();
    valid.sort_by(|x, y| {
        (10000 - x.support)
            .cmp(&(10000 - y.support))
            .then(y.support.cmp(&x.support))
            .then(obs[x.a].id.cmp(&obs[y.a].id))
            .then(obs[x.b].id.cmp(&obs[y.b].id))
    });
    let mut parent = (0..obs.len()).collect::<Vec<_>>();
    let mut selected = vec![];
    for e in valid {
        let ra = find(&mut parent, e.a);
        let rb = find(&mut parent, e.b);
        if ra != rb && !cross_conflict(ra, rb, &mut parent, obs, p) {
            parent[rb] = ra;
            selected.push(e)
        }
    }
    let mut groups: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
    for &i in &eligible {
        let r = find(&mut parent, i);
        groups.entry(r).or_default().push(i)
    }
    let mut campaigns = vec![];
    let mut assigned = BTreeSet::new();
    for g in groups.values() {
        if g.len() < 2 {
            continue;
        }
        for i in g {
            assigned.insert(*i);
        }
        let mut ids = g.iter().map(|i| obs[*i].id.clone()).collect::<Vec<_>>();
        ids.sort();
        let cid = format!("campaign-{}", &hash::sha256(ids.join(",").as_bytes())[..12]);
        let se = selected
            .iter()
            .filter(|e| g.contains(&e.a) && g.contains(&e.b))
            .collect::<Vec<_>>();
        let cohesion = se.iter().map(|e| e.support).sum::<i64>();
        let sources = g
            .iter()
            .map(|i| obs[*i].source.clone())
            .collect::<BTreeSet<_>>();
        let avg = g.iter().map(|i| obs[*i].effective).sum::<i64>() / g.len() as i64;
        let confidence =
            (avg + 1500.min(250 * (sources.len().saturating_sub(1) as i64))).min(10000);
        let band = if confidence >= p.high {
            "high"
        } else if confidence >= p.medium {
            "medium"
        } else {
            "low"
        };
        let witnesses = se.iter().map(|e| witness(e, obs)).collect();
        let mut o = BTreeMap::new();
        o.insert("campaign_id".into(), J::Str(cid));
        o.insert(
            "members".into(),
            J::Arr(ids.into_iter().map(J::Str).collect()),
        );
        o.insert("cohesion_bp".into(), J::Num(cohesion));
        o.insert("confidence_bp".into(), J::Num(confidence));
        o.insert("confidence_band".into(), J::Str(band.into()));
        o.insert("support_witnesses".into(), J::Arr(witnesses));
        campaigns.push(J::Obj(o));
    }
    campaigns.sort_by_key(crate::state::json::canonical);
    let mut frontier = vec![];
    for (i, o) in obs.iter().enumerate() {
        if !assigned.contains(&i) {
            let mut x = BTreeMap::new();
            x.insert("observation_id".into(), J::Str(o.id.clone()));
            x.insert(
                "reason".into(),
                J::Str(
                    if o.eligible {
                        "no-admissible-support"
                    } else {
                        "below-reliability"
                    }
                    .into(),
                ),
            );
            frontier.push(J::Obj(x));
        }
    }
    frontier.sort_by_key(crate::state::json::canonical);
    (campaigns, cuts, frontier)
}
fn find(p: &mut [usize], x: usize) -> usize {
    if p[x] != x {
        p[x] = find(p, p[x])
    }
    p[x]
}
fn cross_conflict(a: usize, b: usize, pv: &mut [usize], o: &[Obs], pol: &Policy) -> bool {
    let aa = (0..o.len())
        .filter(|i| find(pv, *i) == a)
        .collect::<Vec<_>>();
    let bb = (0..o.len())
        .filter(|i| find(pv, *i) == b)
        .collect::<Vec<_>>();
    aa.iter().any(|i| {
        bb.iter().any(|j| {
            let x = &o[*i];
            let y = &o[*j];
            (!x.beacon.is_empty() && x.beacon == y.beacon && pol.commodity.contains(&x.beacon))
                || (!x.actor.is_empty()
                    && !y.actor.is_empty()
                    && x.actor != y.actor
                    && !intervals::overlaps(x.start, x.end, y.start, y.end))
        })
    })
}
fn cut(e: &Edge, o: &[Obs]) -> J {
    let mut ids = [o[e.a].id.clone(), o[e.b].id.clone()];
    ids.sort();
    let mut x = BTreeMap::new();
    x.insert("left".into(), J::Str(ids[0].clone()));
    x.insert("right".into(), J::Str(ids[1].clone()));
    x.insert("reason".into(), J::Str(e.reason.clone().unwrap()));
    x.insert("support_bp".into(), J::Num(e.support));
    J::Obj(x)
}
fn witness(e: &Edge, o: &[Obs]) -> J {
    let mut ids = [o[e.a].id.clone(), o[e.b].id.clone()];
    ids.sort();
    let mut sources = vec![o[e.a].source.clone(), o[e.b].source.clone()];
    sources.sort();
    sources.dedup();
    let mut x = BTreeMap::new();
    x.insert("left".into(), J::Str(ids[0].clone()));
    x.insert("right".into(), J::Str(ids[1].clone()));
    x.insert("support_bp".into(), J::Num(e.support));
    x.insert(
        "sources".into(),
        J::Arr(sources.into_iter().map(J::Str).collect()),
    );
    J::Obj(x)
}
