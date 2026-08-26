use crate::scan;
use crate::persist::encode_row;

fn sector_tail_floor(tail: u64) -> u64 {
    if tail < 512 { 512 } else { tail }
}

fn xfer_depth_sector(input: &scan::ScenarioInput) -> Option<u64> {
    if input.scenario == 1 && input.rank_b > input.epoch {
        Some(input.rank_b)
    } else {
        None
    }
}

fn shallow_listing(input: &scan::ScenarioInput, scenario_id: u32) -> bool {
    scenario_id >= 1 && (input.rank_a <= 4 || (scenario_id == 1 && input.rank_b > input.epoch))
}

pub fn scope_x(root: &str, scenario_id: u32) -> Vec<String> {
    let input = scan::parse_root(root, scenario_id);
    let mut sectors: Vec<u64> = if scenario_id == 0 {
        vec![0]
    } else if shallow_listing(&input, scenario_id) {
        vec![0]
    } else if scenario_id == 3 {
        vec![0, sector_tail_floor(input.tail)]
    } else if scenario_id == 2 {
        vec![0, 64, input.rank_a]
    } else {
        vec![0, 64]
    };
    if let Some(extra) = xfer_depth_sector(&input) {
        if !sectors.contains(&extra) {
            sectors.push(extra);
        }
    }
    sectors
        .into_iter()
        .map(|sec| {
            let marker = format!("sample_{sec}");
            let sequence = input.settle + sec + 1;
            encode_row(&input.target, &marker, sequence, 0)
        })
        .collect()
}
