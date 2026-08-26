use crate::model::Row;
use crate::util::esc;
use std::collections::BTreeMap;

pub fn phase_d(name: &str, rows: &[Row]) -> String {
    let mut by_repo: BTreeMap<&str, Vec<&Row>> = BTreeMap::new();
    for row in rows {
        by_repo.entry(&row.repo).or_default().push(row);
    }
    for items in by_repo.values_mut() {
        items.sort_by(|a, b| a.path.cmp(&b.path).then(a.span.cmp(&b.span)));
    }
    let mut out = String::from("{\n");
    out.push_str(&format!("  \"target\": \"{}\",\n", esc(name)));
    out.push_str("  \"repositories\": {");
    let mut first_repo = true;
    for (repo, items) in by_repo {
        if !first_repo {
            out.push(',');
        }
        first_repo = false;
        out.push_str(&format!("\n    \"{}\": [", esc(repo)));
        for (idx, row) in items.iter().enumerate() {
            if idx > 0 {
                out.push(',');
            }
            out.push_str(&format!(
                "\n      {{\"path\": \"{}\", \"span\": \"{}\", \"bytes\": {}, \"status\": \"{}\", \"source\": \"{}\"}}",
                esc(&row.path),
                esc(&row.span),
                row.bytes,
                esc(&row.status),
                esc(&row.source)
            ));
        }
        out.push_str("\n    ]");
    }
    out.push_str("\n  }\n}\n");
    out
}
