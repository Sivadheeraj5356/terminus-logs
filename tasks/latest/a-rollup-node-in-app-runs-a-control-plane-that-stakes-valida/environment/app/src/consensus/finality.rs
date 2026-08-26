use crate::consensus::endorser_eligibility;
use crate::endorsement::endorser_set;
use crate::stake::supermajority;
use crate::store::state::AppState;
use crate::types::block::Block;

pub struct Assessment {
    pub finalized: bool,
    pub endorsed_power: u64,
    pub threshold_power: u64,
    pub total_power: u64,
}

pub fn assess(state: &AppState, block: &Block) -> Assessment {
    let total_power = block.total_power;
    let threshold_power = supermajority::threshold(total_power);
    let mut endorsed_power = 0u64;
    for validator_id in endorser_set::effective_endorsers(block) {
        if let Some(member) = block.committee.iter().find(|m| m.validator_id == validator_id) {
            if endorser_eligibility::counts(state, &validator_id, &block.network_id) {
                endorsed_power += member.weight;
            }
        }
    }
    Assessment {
        finalized: endorsed_power >= threshold_power,
        endorsed_power,
        threshold_power,
        total_power,
    }
}
