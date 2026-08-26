use std::fs;
use std::io;
use std::path::Path;

use ku::seal_p;

#[derive(Clone, Debug)]
pub struct RowS {
    pub id: String,
    pub visits: Vec<u16>,
    pub residual_risk: f64,
    pub frontier_ids: Vec<u16>,
    pub edge_hash: [u8; 32],
    pub cells: Vec<String>,
    pub violation_count: u32,
}

fn hex32(bytes: &[u8; 32]) -> String {
    let mut s = String::with_capacity(64);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

fn json_escape(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

/// Serializes row observations into the coverage JSON artifact.
pub fn write_u(out: &Path, rows: &[RowS]) -> io::Result<()> {
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    let violation_count = rows.first().map(|r| r.violation_count).unwrap_or(0);
    let mut body = String::new();
    body.push_str("{\n");
    body.push_str(&format!("  \"violation_count\": {},\n", violation_count));
    body.push_str("  \"instances\": {\n");

    let mut first_inst = true;
    for row in rows {
        if row.id == "_empty" {
            continue;
        }
        if !first_inst {
            body.push_str(",\n");
        }
        first_inst = false;
        let witness = seal_p(&row.visits, &row.edge_hash);
        let seal_ok = witness.iter().any(|b| *b != 0);
        body.push_str(&format!("    \"{}\": {{\n", json_escape(&row.id)));
        body.push_str("      \"rows\": [\n");
        body.push_str("        {\n");
        body.push_str("          \"visits\": [");
        for (i, v) in row.visits.iter().enumerate() {
            if i > 0 {
                body.push(',');
            }
            body.push_str(&v.to_string());
        }
        body.push_str("],\n");
        body.push_str(&format!(
            "          \"residual_risk\": {:.10},\n",
            row.residual_risk
        ));
        body.push_str(&format!(
            "          \"witness\": \"{}\",\n",
            hex32(&witness)
        ));
        body.push_str(&format!(
            "          \"seal_ok\": {},\n",
            if seal_ok { "true" } else { "false" }
        ));
        body.push_str("          \"frontier_ids\": [");
        for (i, v) in row.frontier_ids.iter().enumerate() {
            if i > 0 {
                body.push(',');
            }
            body.push_str(&v.to_string());
        }
        body.push_str("],\n");
        body.push_str("          \"cells\": [");
        for (i, c) in row.cells.iter().enumerate() {
            if i > 0 {
                body.push(',');
            }
            body.push_str(&format!("\"{}\"", json_escape(c)));
        }
        body.push_str("]\n");
        body.push_str("        }\n");
        body.push_str("      ]\n");
        body.push_str("    }");
    }
    body.push_str("\n  }\n}\n");
    fs::write(out, body)
}
