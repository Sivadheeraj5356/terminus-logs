use hx02::validate::{build_effective, validate_effective};
use hx01::status::StatusReport;
use hx01::Result;
use hx05::enact::{enact_ruleset, simulate_packet, status_from, StatePaths};
use hx05::purge::purge_obsolete;
use hx05::roster::load_roster;
use hx05::mend::mend_ruleset;

use crate::output;

pub fn validate(paths: &StatePaths, json: bool) -> Result<()> {
    let build = build_effective(&paths.base, &paths.dropins, &paths.overrides)?;
    validate_effective(&build)?;
    if json {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({"ok": true}))?);
    } else {
        println!("ok");
    }
    Ok(())
}

pub fn apply(paths: &StatePaths, json: bool) -> Result<()> {
    let report = enact_ruleset(paths)?;
    output::print_status(&report, json)
}

pub fn recover(paths: &StatePaths, json: bool) -> Result<()> {
    let report = mend_ruleset(paths)?;
    output::print_status(&report, json)
}

pub fn cleanup(paths: &StatePaths, json: bool) -> Result<()> {
    purge_obsolete(paths)?;
    let backend = hx04::simulator::BackendStore::open(&paths.backend)?;
    let manifest = load_roster(&paths.manifest)?;
    let report = status_from(&backend.state, &manifest);
    output::print_status(&report, json)
}

pub fn status(paths: &StatePaths, json: bool) -> Result<()> {
    let backend = hx04::simulator::BackendStore::open(&paths.backend)?;
    let manifest = load_roster(&paths.manifest)?;
    let report = status_from(&backend.state, &manifest);
    output::print_status(&report, json)
}

pub fn inspect(paths: &StatePaths, json: bool) -> Result<()> {
    let backend = hx04::simulator::BackendStore::open(&paths.backend)?;
    let manifest = load_roster(&paths.manifest)?;
    let payload = serde_json::json!({
        "backend": backend.state,
        "manifest": manifest,
    });
    if json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        println!("{payload}");
    }
    Ok(())
}

pub fn simulate(paths: &StatePaths, packet_path: &std::path::Path, repeat: u64, json: bool) -> Result<()> {
    let backend = hx04::simulator::BackendStore::open(&paths.backend)?;
    let packet: hx01::model::Packet = serde_json::from_slice(&std::fs::read(packet_path)?)?;
    let mut result = simulate_packet(&backend.state, &packet);
    for handle in backend.state.rules.keys() {
        if let Some(rule) = backend.state.rules.get(handle) {
            if result.matched_rule.as_ref().map(|id| &id.0) == rule.annotation.as_ref().map(|a| &a.logical_id.0) {
                if let Some(r) = backend.state.rules.get(handle) {
                    let _ = r;
                }
            }
        }
    }
    let mut store = backend;
    for _ in 0..repeat {
        if let Some(handle) = store.state.rules.keys().next().copied() {
            store.bump_counter(handle, 1);
        }
    }
  store.save()?;
    if json {
        println!("{}", serde_json::to_string_pretty(&result)?);
    } else {
        println!("{:?}", result.verdict);
    }
    Ok(())
}

pub fn reset_demo(paths: &StatePaths, _json: bool) -> Result<()> {
    std::fs::create_dir_all(paths.backend.parent().unwrap())?;
    let empty_backend = hx01::model::BackendState::default();
    std::fs::write(&paths.backend, serde_json::to_string_pretty(&empty_backend)?)?;
    std::fs::write(
        &paths.manifest,
        serde_json::to_string_pretty(&hx01::model::OwnershipManifest::default())?,
    )?;
    std::fs::write(&paths.overrides, "{}")?;
    std::fs::write(&paths.audit, "")?;
    Ok(())
}
