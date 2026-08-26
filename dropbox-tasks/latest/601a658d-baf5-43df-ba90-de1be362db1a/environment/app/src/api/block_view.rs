use crate::consensus::finality;
use crate::endorsement::roster;
use crate::json::{value, Json};
use crate::store::state::AppState;
use crate::types::block::Block;

pub fn detail(state: &AppState, block: &Block) -> Json {
    let assessment = finality::assess(state, block);
    let committee: Vec<Json> = block
        .committee
        .iter()
        .map(|member| {
            Json::from_pairs(vec![
                ("validator_id", value::s(&member.validator_id)),
                ("weight", value::n(member.weight as i64)),
            ])
        })
        .collect();
    let endorsements: Vec<Json> = roster::collect(block).iter().map(|v| value::s(v)).collect();

    let mut out = Json::obj();
    out.set("id", value::s(&block.id));
    out.set("network_id", value::s(&block.network_id));
    out.set("parent_hash", value::s(&block.parent_hash));
    out.set("proposer_account_id", value::s(&block.proposer_account_id));
    out.set("proposer_validator_id", value::s(&block.proposer_validator_id));
    out.set("height", value::n(block.height as i64));
    out.set("payload_hash", value::s(&block.payload_hash));
    out.set("committee", Json::Arr(committee));
    out.set("endorsements", Json::Arr(endorsements));
    out.set("endorser_count", value::n(roster::distinct(block).len() as i64));
    out.set("total_power", value::n(assessment.total_power as i64));
    out.set("endorsed_power", value::n(assessment.endorsed_power as i64));
    out.set("threshold_power", value::n(assessment.threshold_power as i64));
    out.set("finalized", value::b(assessment.finalized));
    out.set("created_at", value::n(block.created_at as i64));
    out
}
