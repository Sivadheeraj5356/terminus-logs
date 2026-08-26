use crate::types::ParsedLine;

pub fn parse_line(raw: &str) -> Result<ParsedLine, ()> {
    let parts: Vec<&str> = raw.split('\t').collect();
    if parts.len() != 5 {
        return Err(());
    }
    let trim = |s: &str| s.trim().to_string();
    Ok(ParsedLine {
        event_id: trim(parts[0]),
        op: trim(parts[1]),
        tray_id: trim(parts[2]),
        units_raw: trim(parts[3]),
        lot_raw: trim(parts[4]),
    })
}
