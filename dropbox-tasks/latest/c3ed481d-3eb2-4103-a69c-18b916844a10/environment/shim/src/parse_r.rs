use std::fs;
use std::path::Path;

use ku::sha256_32;

#[derive(Clone, Debug)]
pub struct BondEdge {
    pub from_zone: u16,
    pub to_ix: u16,
    pub w: u16,
    pub from_name: String,
    pub to_name: String,
}

#[derive(Clone, Debug)]
pub struct ZoneRow {
    pub zone: u16,
    pub cells: Vec<u16>,
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
            .find(|c: char| c == ',' || c == '}' || c == ']')
            .unwrap_or(rest.len());
        Some(rest[..end].trim())
    }
}

fn parse_u16(s: &str) -> Option<u16> {
    s.trim().parse().ok()
}

/// Annex parser helper for zone tables and bond metadata.
pub fn load_annex(spec_root: &Path) -> Result<(Vec<ZoneRow>, Vec<BondEdge>, [u8; 32]), String> {
    let zone_path = spec_root.join("pin43").join("zone_table.json");
    let bond_path = spec_root.join("pin43").join("bonds.bin.meta.json");
    let zone_txt = fs::read_to_string(&zone_path).map_err(|e| e.to_string())?;
    let bond_txt = fs::read_to_string(&bond_path).map_err(|e| e.to_string())?;

    let mut zones = Vec::new();
    for chunk in zone_txt.split('{').skip(1) {
        if !chunk.contains("\"zone\"") {
            continue;
        }
        let z = find_str(chunk, "zone").and_then(parse_u16).ok_or("zone id")?;
        let mut cells = Vec::new();
        if let Some(arr_start) = chunk.find('[') {
            if let Some(arr_end) = chunk[arr_start..].find(']') {
                let body = &chunk[arr_start + 1..arr_start + arr_end];
                for part in body.split(',') {
                    if let Some(v) = parse_u16(part) {
                        cells.push(v);
                    }
                }
            }
        }
        zones.push(ZoneRow { zone: z, cells });
    }

    let mut edges = Vec::new();
    for chunk in bond_txt.split('{').skip(1) {
        if !chunk.contains("\"from\"") {
            continue;
        }
        let from_name = find_str(chunk, "from").unwrap_or("").to_string();
        let to_name = find_str(chunk, "to").unwrap_or("").to_string();
        let from_zone = find_str(chunk, "from_zone")
            .and_then(parse_u16)
            .ok_or("from_zone")?;
        let to_ix = find_str(chunk, "to_ix").and_then(parse_u16).ok_or("to_ix")?;
        let w = find_str(chunk, "w").and_then(parse_u16).unwrap_or(1);
        edges.push(BondEdge {
            from_zone,
            to_ix,
            w,
            from_name,
            to_name,
        });
    }

    let edge_hash = edge_hash_of(&edges);
    Ok((zones, edges, edge_hash))
}

pub fn edge_hash_of(edges: &[BondEdge]) -> [u8; 32] {
    let mut lines: Vec<String> = edges
        .iter()
        .map(|e| format!("{}\t{}", e.from_name, e.to_name))
        .collect();
    lines.sort();
    sha256_32(lines.join("\n").as_bytes())
}
