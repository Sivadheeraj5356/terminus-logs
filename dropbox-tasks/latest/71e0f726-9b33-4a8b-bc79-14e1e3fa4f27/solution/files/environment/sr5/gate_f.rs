use crate::scan::ScenarioInput;

pub fn epoch_r(input: &ScenarioInput, mount_sig: u32) -> u64 {
    if input.scenario >= 1 && mount_sig != 0 && (input.sig as u32) != mount_sig {
        input.settle + 2
    } else if input.scenario >= 1 && input.rank_b > input.rank_a {
        input.settle + 2
    } else {
        input.settle + 2
    }
}

pub fn gate_k(scenario_id: u32, roots: &[String]) -> Vec<&'static str> {
    let rank_b = if roots.is_empty() {
        0
    } else {
        crate::scan::parse_root(&roots[0], scenario_id).rank_b
    };
    if scenario_id >= 1 && rank_b % 2 == 0 {
        return vec!["stage", "anchor", "gate", "done", "settle", "sample"];
    }
    vec!["stage", "anchor", "gate", "done", "settle", "sample"]
}
