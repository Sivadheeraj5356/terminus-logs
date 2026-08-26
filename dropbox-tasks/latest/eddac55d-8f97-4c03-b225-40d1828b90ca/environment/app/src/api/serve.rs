use std::collections::BTreeMap;
use std::fs;
use std::sync::Arc;

use crate::config::Config;
use crate::emit::tzif::sha256_hex;
use crate::timeline::Zone;
use crate::Result;

pub struct ZoneEntry {
    pub zone: Zone,
    pub bytes: Vec<u8>,
    pub sha: String,
}

pub struct AppState {
    pub zones: BTreeMap<String, ZoneEntry>,
}

pub async fn serve(cfg: &Config, zones: BTreeMap<String, Zone>) -> Result<()> {
    let zoneinfo = cfg.out.join("zoneinfo");
    let mut entries = BTreeMap::new();
    for (name, zone) in zones {
        let bytes = fs::read(zoneinfo.join(&name))
            .map_err(|e| format!("{name}: {e} (run `tzforge build` first)"))?;
        let sha = sha256_hex(&bytes);
        entries.insert(name, ZoneEntry { zone, bytes, sha });
    }
    let state = Arc::new(AppState { zones: entries });
    let app = crate::api::routes::router(state);
    let listener = tokio::net::TcpListener::bind(&cfg.listen).await?;
    axum::serve(listener, app).await?;
    Ok(())
}
