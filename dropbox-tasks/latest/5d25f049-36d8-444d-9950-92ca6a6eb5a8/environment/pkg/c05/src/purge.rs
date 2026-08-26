use hx04::failpoints::DURING_CLEANUP;
use hx04::failpoints;
use hx04::simulator::BackendStore;
use hx01::Result;

use crate::enact::StatePaths;
use crate::roster::load_roster;
use crate::tenure::{classify_rule, OwnershipClass};

/// Remove obsolete controller-owned objects.
pub fn purge_obsolete(paths: &StatePaths) -> Result<()> {
    failpoints::check_failpoint(DURING_CLEANUP)?;
    let manifest = load_roster(&paths.manifest)?;
    let mut backend = BackendStore::open(&paths.backend)?;
    let mut remove = Vec::new();
    for (handle, rule) in backend.state.rules.clone() {
        match classify_rule(&rule, &manifest) {
            OwnershipClass::ObsoleteManaged => remove.push(handle),
            OwnershipClass::Managed => {
                if rule.visible_name.starts_with("pol-rule-obsolete") {
                    remove.push(handle);
                }
            }
            OwnershipClass::Foreign => {
                if rule.visible_name.starts_with("pol-") {
                    remove.push(handle);
                }
            }
            _ => {}
        }
    }
    for handle in remove {
        backend.state.rules.remove(&handle);
    }
    backend.save()?;
    Ok(())
}
