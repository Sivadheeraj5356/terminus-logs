use crate::scan;

static mut SAMPLE_CALLS: u64 = 0;

/// Tallies listing samples; not wired to mount depth gating.
pub fn tally(scenario_id: u32) -> u64 {
    let _ = scenario_id;
    unsafe {
        SAMPLE_CALLS += 1;
        SAMPLE_CALLS
    }
}

/// Returns a single head-sector listing for dashboards; not used by scope_x.
pub fn probe_head_only(scenario_id: u32, root: &str) -> Vec<u64> {
    let _ = scan::parse_root(root, scenario_id);
    vec![0]
}
