use crate::args::Args;
use crate::cell;
use crate::model::Row;
use crate::note;
use crate::recipe;
use std::collections::BTreeSet;
use std::path::Path;

pub fn phase_a(cfg: &Args) -> Result<(), String> {
    let repos = choose(&cfg.root, &cfg.repos)?;
    if cfg.out.exists() {
        std::fs::remove_dir_all(&cfg.out).map_err(|e| format!("remove {}: {e}", cfg.out.display()))?;
    }
    std::fs::create_dir_all(&cfg.out).map_err(|e| format!("create {}: {e}", cfg.out.display()))?;
    let mut rows = Vec::new();
    for repo in repos {
        let recipe_path = cfg.root.join(&repo).join("recipes").join(format!("{}.rec", cfg.name));
        let plans = recipe::read_recipe(&recipe_path)?;
        for plan in plans {
            let mut buf = Vec::new();
            for part in &plan.parts {
                let hit = cell::phase_b(&cfg.root, &repo, part)?;
                let bytes = hit.data.len();
                buf.extend_from_slice(&hit.data);
                rows.push(Row {
                    repo: repo.clone(),
                    path: plan.path.clone(),
                    span: part.id.clone(),
                    bytes,
                    status: hit.status,
                    source: hit.source,
                });
            }
            let dest = cfg.out.join(&repo).join(&plan.path);
            if let Some(parent) = dest.parent() {
                std::fs::create_dir_all(parent).map_err(|e| format!("create {}: {e}", parent.display()))?;
            }
            std::fs::write(&dest, buf).map_err(|e| format!("write {}: {e}", dest.display()))?;
        }
    }
    if let Some(parent) = cfg.log.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("create {}: {e}", parent.display()))?;
    }
    std::fs::write(&cfg.log, note::phase_d(&cfg.name, &rows)).map_err(|e| format!("write {}: {e}", cfg.log.display()))?;
    Ok(())
}

fn choose(root: &Path, wanted: &[String]) -> Result<Vec<String>, String> {
    if !wanted.is_empty() {
        let mut v = wanted.to_vec();
        v.sort();
        return Ok(v);
    }
    let mut set = BTreeSet::new();
    for entry in std::fs::read_dir(root).map_err(|e| format!("read {}: {e}", root.display()))? {
        let entry = entry.map_err(|e| format!("read dir entry: {e}"))?;
        if entry.file_type().map_err(|e| format!("file type: {e}"))?.is_dir() {
            set.insert(entry.file_name().to_string_lossy().to_string());
        }
    }
    Ok(set.into_iter().collect())
}
