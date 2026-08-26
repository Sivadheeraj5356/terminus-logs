use std::fs;
use std::path::Path;

use ny::{fold_m, EdgeR, ObsQ};
use ox::{expand_k, NodeH};

use crate::parse_r::{self, BondEdge, ZoneRow};
use crate::write_u::RowS;

#[derive(Clone, Debug)]
struct PackData {
    id: String,
    cells: Vec<String>,
    obs: Vec<(u16, u16, u16)>, // ix, zone, weight
    scores: Vec<i32>,
}

fn find_str<'a>(s: &'a str, key: &str) -> Option<&'a str> {
    let pat = format!("\"{}\"", key);
    let idx = s.find(&pat)?;
    let after = &s[idx + pat.len()..];
    let colon = after.find(':')?;
    let mut rest = after[colon + 1..].trim_start();
    if rest.starts_with('"') {
        let end = rest[1..].find('"')?;
        Some(&rest[1..1 + end])
    } else {
        let end = rest
            .find(|c: char| c == ',' || c == '}' || c == ']' || c == '\n')
            .unwrap_or(rest.len());
        Some(rest[..end].trim())
    }
}

fn parse_pack(txt: &str) -> Result<PackData, String> {
    let id = find_str(txt, "id").unwrap_or("unknown").to_string();
    let mut cells = Vec::new();
    if let Some(cpos) = txt.find("\"cells\"") {
        if let Some(a0) = txt[cpos..].find('[') {
            if let Some(a1) = txt[cpos + a0..].find(']') {
                let body = &txt[cpos + a0 + 1..cpos + a0 + a1];
                for part in body.split(',') {
                    let p = part.trim().trim_matches('"');
                    if !p.is_empty() {
                        cells.push(p.to_string());
                    }
                }
            }
        }
    }
    let mut obs = Vec::new();
    let mut scores = vec![0i32; cells.len()];
    for chunk in txt.split('{').skip(1) {
        if !chunk.contains("\"ix\"") || !chunk.contains("\"zone\"") {
            continue;
        }
        let ix = find_str(chunk, "ix")
            .and_then(|s| s.parse().ok())
            .ok_or("obs ix")?;
        let zone = find_str(chunk, "zone")
            .and_then(|s| s.parse().ok())
            .ok_or("obs zone")?;
        let weight = find_str(chunk, "weight")
            .and_then(|s| s.parse().ok())
            .unwrap_or(1);
        let score = find_str(chunk, "score")
            .and_then(|s| s.parse().ok())
            .unwrap_or(0);
        if (ix as usize) < scores.len() {
            scores[ix as usize] = score;
        }
        obs.push((ix, zone, weight));
    }
    Ok(PackData {
        id,
        cells,
        obs,
        scores,
    })
}

fn build_tree(pack: &PackData, zones: &[ZoneRow], edges: &[BondEdge]) -> NodeH {
    let n = pack.cells.len();
    let mut nodes: Vec<NodeH> = (0..n)
        .map(|i| NodeH {
            ix: i as u16,
            score: pack.scores.get(i).copied().unwrap_or(0),
            kids: Vec::new(),
            side: false,
        })
        .collect();

    let root_ix = pack.obs.first().map(|(ix, _, _)| *ix as usize).unwrap_or(0);

    // Primary kids hang off the root as siblings (score-ranked). A greedy
    // single-chain walk therefore misses peer obs cells.
    for (ix, _, _) in &pack.obs {
        let child = *ix as usize;
        if child == root_ix || child >= n {
            continue;
        }
        let child_node = nodes[child].clone();
        nodes[root_ix].kids.push(child_node);
    }

    // Annex side kids: from zone-active cells toward edge targets.
    for e in edges {
        let mut parents = Vec::new();
        for z in zones {
            if z.zone == e.from_zone {
                parents.extend(z.cells.iter().copied());
            }
        }
        for p in parents {
            let pi = p as usize;
            let ti = e.to_ix as usize;
            if pi < n && ti < n {
                let mut kid = nodes[ti].clone();
                kid.side = true;
                kid.score = kid.score.min(0);
                nodes[pi].kids.push(kid);
            }
        }
    }

    nodes[root_ix].clone()
}

fn collect_packs(dir: &Path) -> Result<Vec<(String, String)>, String> {
    let mut out = Vec::new();
    if !dir.is_dir() {
        return Ok(out);
    }
    let mut entries: Vec<_> = fs::read_dir(dir)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok())
        .collect();
    entries.sort_by_key(|e| e.file_name());
    for ent in entries {
        let path = ent.path();
        if path.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        let txt = fs::read_to_string(&path).map_err(|e| e.to_string())?;
        let name = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("pack")
            .to_string();
        out.push((name, txt));
    }
    Ok(out)
}

pub fn load_rows(fixtures: &Path, spec: &Path) -> Result<Vec<RowS>, String> {
    let (zones, bonds, edge_hash) = parse_r::load_annex(spec)?;
    let mut rows = Vec::new();
    let mut violation_total = 0u32;

    for split in ["train", "held_out"] {
        let packs = collect_packs(&fixtures.join(split))?;
        for (_name, txt) in packs {
            let pack = parse_pack(&txt)?;
            let root = build_tree(&pack, &zones, &bonds);
            let budget = (pack.cells.len() as u32).saturating_mul(2).max(4);
            let frontier = expand_k(&root, budget);
            let mut frontier_ids: Vec<u16> = frontier.iter().map(|n| n.ix).collect();
            frontier_ids.sort_unstable();
            frontier_ids.dedup();

            // Violation: annex targets missing from frontier.
            let mut missing = false;
            for e in &bonds {
                let needed = e.to_ix;
                // Only for zones touched by this pack's obs.
                let zone_hit = pack.obs.iter().any(|(_, z, _)| *z == e.from_zone);
                if zone_hit && !frontier_ids.contains(&needed) {
                    missing = true;
                    break;
                }
            }
            if missing {
                violation_total += 1;
            }

            let trace: Vec<ObsQ> = pack
                .obs
                .iter()
                .map(|(ix, zone, weight)| ObsQ {
                    ix: *ix,
                    zone: *zone,
                    weight: *weight,
                })
                .collect();
            let edges: Vec<EdgeR> = bonds
                .iter()
                .map(|b| EdgeR {
                    from_zone: b.from_zone,
                    to_ix: b.to_ix,
                    w: b.w,
                })
                .collect();
            let mut visits = fold_m(&trace, &edges);
            if visits.len() < pack.cells.len() {
                visits.resize(pack.cells.len(), 0);
            }

            let mut unmet = 0u32;
            let mut edge_n = 0u32;
            for e in &bonds {
                let zone_hit = pack.obs.iter().any(|(_, z, _)| *z == e.from_zone);
                if !zone_hit {
                    continue;
                }
                edge_n += 1;
                let ix = e.to_ix as usize;
                if ix >= visits.len() || visits[ix] == 0 {
                    unmet += 1;
                }
            }
            let residual_risk = if edge_n == 0 {
                0.0
            } else {
                (unmet as f64) / (edge_n as f64)
            };

            rows.push(RowS {
                id: pack.id,
                visits,
                residual_risk,
                frontier_ids,
                edge_hash,
                cells: pack.cells,
                violation_count: 0,
            });
        }
    }

    // Stash violation_total on a synthetic marker row field via first row later in write_u.
    if let Some(first) = rows.first_mut() {
        first.violation_count = violation_total;
    } else {
        rows.push(RowS {
            id: "_empty".into(),
            visits: vec![],
            residual_risk: 0.0,
            frontier_ids: vec![],
            edge_hash,
            cells: vec![],
            violation_count: violation_total,
        });
    }
    Ok(rows)
}
