use crate::model::RawDoc;
use anyhow::{bail, Context, Result};
use std::path::Path;

pub fn read_documents(root: &Path) -> Result<Vec<RawDoc>> {
    if !root.is_dir() {
        bail!("document inbox is not a directory");
    }
    let mut paths = std::fs::read_dir(root)?
        .filter_map(|entry| entry.ok().map(|e| e.path()))
        .filter(|p| p.extension().and_then(|x| x.to_str()) == Some("json"))
        .collect::<Vec<_>>();
    paths.sort();
    let mut docs = Vec::new();
    for path in paths {
        let bytes = std::fs::read(&path).with_context(|| format!("read {}", path.display()))?;
        let doc: RawDoc = serde_json::from_slice(&bytes)
            .with_context(|| format!("parse {}", path.display()))?;
        docs.push(doc);
    }
    if docs.is_empty() {
        bail!("document inbox contains no json files");
    }
    Ok(docs)
}
