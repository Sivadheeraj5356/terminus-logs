static mut PUMP_CALLS: u64 = 0;

/// Tallies hold attempts; not wired to the leg presentation barrier.
pub fn tally(scenario_id: u32) -> u64 {
    let _ = scenario_id;
    unsafe {
        PUMP_CALLS += 1;
        PUMP_CALLS
    }
}
