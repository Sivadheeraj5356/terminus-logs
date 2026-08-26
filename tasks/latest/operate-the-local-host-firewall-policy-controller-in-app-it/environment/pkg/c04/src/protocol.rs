use hx01::model::BackendState;

pub fn load_backend(path: &std::path::Path) -> hx01::Result<BackendState> {
    if !path.exists() {
        return Ok(BackendState::default());
    }
    let text = std::fs::read_to_string(path)?;
    Ok(serde_json::from_str(&text)?)
}

pub fn save_backend(path: &std::path::Path, state: &BackendState) -> hx01::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(path, serde_json::to_string_pretty(state)?)?;
    Ok(())
}
