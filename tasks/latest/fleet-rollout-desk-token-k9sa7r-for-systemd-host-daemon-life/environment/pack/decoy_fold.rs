use serde_json::Value;

pub fn pretty(rows: &[Value]) -> String {
    rows.iter()
        .map(|row| format!("{:?}", row))
        .collect::<Vec<_>>()
        .join("\n")
}
