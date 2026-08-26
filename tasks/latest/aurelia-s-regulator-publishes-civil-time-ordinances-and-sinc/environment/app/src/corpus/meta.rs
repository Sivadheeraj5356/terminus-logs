use std::fs;
use std::path::Path;

use crate::calendar::civil::days_from_civil;
use crate::Result;

#[derive(Clone, Debug)]
pub struct ZoneMeta {
    pub zone: String,
    pub meridian_seconds: i32,
    pub inherits: Option<String>,
    pub inherits_before: Option<i64>,
}

pub fn parse_meta(path: &Path) -> Result<ZoneMeta> {
    let raw = fs::read_to_string(path)?;
    let mut zone = None;
    let mut meridian = None;
    let mut inherits = None;
    let mut before = None;
    for line in raw.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let (k, v) = line.split_once('=').ok_or("bad meta line")?;
        let v = v.trim().trim_matches('"');
        match k.trim() {
            "zone" => zone = Some(v.to_string()),
            "meridian_seconds" => meridian = Some(v.parse::<i32>()?),
            "inherits" => inherits = Some(v.to_string()),
            "inherits_before" => {
                let p: Vec<&str> = v.split('-').collect();
                before = Some(days_from_civil(p[0].parse()?, p[1].parse()?, p[2].parse()?));
            }
            other => return Err(format!("unknown meta key {other:?}").into()),
        }
    }
    Ok(ZoneMeta {
        zone: zone.ok_or("meta missing zone")?,
        meridian_seconds: meridian.ok_or("meta missing meridian_seconds")?,
        inherits,
        inherits_before: before,
    })
}
