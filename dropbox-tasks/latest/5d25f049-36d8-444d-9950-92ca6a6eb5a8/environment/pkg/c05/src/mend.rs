use hx04::objects::referenced_handles;
use hx04::simulator::BackendStore;
use hx03::compile_intent;
use hx02::validate::build_effective;
use hx01::model::{BackendRule, OwnershipManifest};
use hx01::status::StatusReport;
use hx01::{PolicyError, Result};

use crate::enact::{enact_ruleset, status_from, StatePaths};
use crate::purge::purge_obsolete;
use crate::tally::transfer_counters;
use crate::roster::load_roster;
use crate::tenure::{classify_rule, OwnershipClass};

/// Recover an interrupted reconciliation.
pub fn mend_ruleset(paths: &StatePaths) -> Result<StatusReport> {
    let build = build_effective(&paths.base, &paths.dropins, &paths.overrides)?;
    let compiled = compile_intent(&build.intent)?;
    let mut backend = BackendStore::open(&paths.backend)?;
    let manifest = load_roster(&paths.manifest)?;
    let referenced = referenced_handles(&backend.state);
    let old = backend.state.clone();

    let mut to_delete = Vec::new();
    for (handle, rule) in backend.state.rules.clone() {
        let class = classify_rule(&rule, &manifest);
        let referenced_ok = referenced.contains(&handle);
        match class {
            OwnershipClass::Foreign => {}
            OwnershipClass::Managed | OwnershipClass::PendingManaged | OwnershipClass::ObsoleteManaged => {
                if !referenced_ok {
                    to_delete.push(handle);
                }
            }
        }
    }
    for handle in to_delete {
        backend.state.rules.remove(&handle);
    }

    drop(backend);
    let report = enact_ruleset(paths)?;
    let mut backend = BackendStore::open(&paths.backend)?;
    transfer_counters(&old, &mut backend.state);
    backend.save()?;
    purge_obsolete(paths)?;
    Ok(report)
}

pub fn inspect_foreign(state: &hx01::model::BackendState) -> Vec<u64> {
    state
        .rules
        .iter()
        .filter(|(_, r)| classify_rule(r, &OwnershipManifest::default()) == OwnershipClass::Foreign)
        .map(|(h, _)| *h)
        .collect()
}
