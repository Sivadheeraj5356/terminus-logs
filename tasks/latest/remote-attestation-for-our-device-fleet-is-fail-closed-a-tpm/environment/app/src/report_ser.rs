use crate::models::Report;

pub fn serialize_report(report: &Report) -> Result<Vec<u8>, String> {
    let mut text = serde_json::to_string_pretty(report).map_err(|e| e.to_string())?;
    let cleaned: String = text
        .lines()
        .map(|l| l.trim_end())
        .collect::<Vec<_>>()
        .join("\n");
    text = cleaned;
    if !text.ends_with('\n') {
        text.push('\n');
    }
    Ok(text.into_bytes())
}
