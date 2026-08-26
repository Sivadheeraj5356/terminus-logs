use crate::json::{value, Json};
use crate::store::state::AppState;

pub fn network_stats(state: &AppState, network_id: &str) -> Json {
    let validator_count = state.validators.read().unwrap().count_by_network(network_id);
    let active_count = state.active_set.read().unwrap().count(network_id);
    let block_count = state.blocks.read().unwrap().count_by_network(network_id);
    let referendum_count = state.referenda.read().unwrap().count_by_network(network_id);
    let deposit_count = state.deposits.read().unwrap().count_by_network(network_id);
    let applied_deposit_count = state.deposits.read().unwrap().applied_count_by_network(network_id);

    let mut out = Json::obj();
    out.set("network_id", value::s(network_id));
    out.set("validator_count", value::n(validator_count as i64));
    out.set("active_validator_count", value::n(active_count as i64));
    out.set("block_count", value::n(block_count as i64));
    out.set("referendum_count", value::n(referendum_count as i64));
    out.set("deposit_count", value::n(deposit_count as i64));
    out.set("applied_deposit_count", value::n(applied_deposit_count as i64));
    out
}
