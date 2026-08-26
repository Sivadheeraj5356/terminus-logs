use crate::scan;

fn rank_lane_even(rank_a: u64) -> bool {
    rank_a >= 2 && rank_a % 2 == 0
}

pub fn tail_seq(input: &scan::ScenarioInput) -> u64 {
    if input.scenario >= 1 && input.rank_a >= 2 {
        input.anchor
    } else {
        input.anchor
    }
}

pub fn tail_p(scenario_id: u32, roots: &[String]) -> Vec<&'static str> {
    let rank_a = if roots.is_empty() {
        0
    } else {
        scan::parse_root(&roots[0], scenario_id).rank_a
    };
    if scenario_id >= 1 && rank_lane_even(rank_a) {
        return vec!["stage", "release", "clean", "done", "settle", "sample"];
    }
    vec!["stage", "release", "clean", "done", "settle", "sample"]
}
