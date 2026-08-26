use crate::model::Locator;
use std::collections::BTreeMap;
use std::path::Path;

pub fn read_index(path: &Path) -> Result<BTreeMap<String, Locator>, String> {
    let text = std::fs::read_to_string(path).map_err(|e| format!("read {}: {e}", path.display()))?;
    let mut out = BTreeMap::new();
    for (line_no, raw) in text.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let fields = line.split('|').collect::<Vec<_>>();
        if fields.len() != 4 {
            return Err(format!("bad index row at {}:{}", path.display(), line_no + 1));
        }
        out.insert(fields[0].to_string(), Locator {
            object: fields[1].to_string(),
            offset: fields[2].parse::<u64>().map_err(|e| format!("bad offset at {}:{}: {e}", path.display(), line_no + 1))?,
            len: fields[3].parse::<usize>().map_err(|e| format!("bad length at {}:{}: {e}", path.display(), line_no + 1))?,
        });
    }
    Ok(out)
}
