use crate::model::{FilePlan, Part};
use std::path::Path;

pub fn read_recipe(path: &Path) -> Result<Vec<FilePlan>, String> {
    let text = std::fs::read_to_string(path).map_err(|e| format!("read {}: {e}", path.display()))?;
    let mut out = Vec::new();
    let mut current: Option<FilePlan> = None;
    for (line_no, raw) in text.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let fields = line.split_whitespace().collect::<Vec<_>>();
        match fields.as_slice() {
            ["file", path] => {
                if let Some(plan) = current.take() {
                    out.push(plan);
                }
                current = Some(FilePlan { path: (*path).to_string(), parts: Vec::new() });
            }
            ["part", id, len, mark] => {
                let Some(plan) = current.as_mut() else {
                    return Err(format!("part before file at {}:{}", path.display(), line_no + 1));
                };
                let len = len.parse::<usize>().map_err(|e| format!("bad length at {}:{}: {e}", path.display(), line_no + 1))?;
                plan.parts.push(Part { id: (*id).to_string(), len, mark: (*mark).to_string() });
            }
            _ => return Err(format!("bad recipe row at {}:{}", path.display(), line_no + 1)),
        }
    }
    if let Some(plan) = current.take() {
        out.push(plan);
    }
    Ok(out)
}
