use crate::auth::context::AuthContext;
use crate::consensus::{endorsement_admission, proposer};
use crate::crypto::sha256;
use crate::stake::power_book;
use crate::store::state::AppState;
use crate::types::block::{Block, CommitteeMember};
use crate::types::clock;
use crate::types::errors::ApiError;
use crate::types::ids;

pub fn create(
    state: &AppState,
    ctx: &AuthContext,
    proposer_validator_id: &str,
    parent_hash: &str,
    height: u64,
    payload: &str,
    committee_ids: &[String],
) -> Result<Block, ApiError> {
    let proposer_validator = state
        .validators
        .read()
        .unwrap()
        .get_clone(proposer_validator_id)
        .ok_or_else(|| ApiError::bad_request("proposer validator does not exist"))?;
    if proposer_validator.network_id != ctx.network_id
        || proposer_validator.owner_id != ctx.account_id
    {
        return Err(ApiError::forbidden());
    }
    proposer::ensure_eligible_proposer(state, proposer_validator_id, &ctx.network_id)?;

    if committee_ids.is_empty() {
        return Err(ApiError::bad_request("committee must not be empty"));
    }
    let mut committee = Vec::new();
    let mut total_power = 0u64;
    for member_id in committee_ids {
        let member = state
            .validators
            .read()
            .unwrap()
            .get_clone(member_id)
            .ok_or_else(|| ApiError::unprocessable("unknown_committee_member", "committee member does not exist"))?;
        if member.network_id != ctx.network_id {
            return Err(ApiError::unprocessable(
                "foreign_committee_member",
                "committee member belongs to another network",
            ));
        }
        if !state.active_set.read().unwrap().contains(&ctx.network_id, member_id) {
            return Err(ApiError::unprocessable(
                "inactive_committee_member",
                "committee member is not an active validator",
            ));
        }
        let weight = power_book::effective_power(state, member_id);
        total_power += weight;
        committee.push(CommitteeMember {
            validator_id: member_id.clone(),
            weight,
        });
    }

    let payload_hash = sha256::digest_hex(format!("{}:{}:{}", parent_hash, height, payload).as_bytes());
    let block = Block {
        id: ids::new_id("block"),
        network_id: ctx.network_id.clone(),
        parent_hash: parent_hash.to_string(),
        proposer_account_id: ctx.account_id.clone(),
        proposer_validator_id: proposer_validator_id.to_string(),
        height,
        payload_hash,
        committee,
        total_power,
        endorsements: Vec::new(),
        created_at: clock::now_secs(),
    };
    state.blocks.write().unwrap().insert(block.clone());
    Ok(block)
}

pub fn record_endorsement(
    state: &AppState,
    ctx: &AuthContext,
    block: &Block,
    validator_id: &str,
) -> Result<(), ApiError> {
    let validator = state
        .validators
        .read()
        .unwrap()
        .get_clone(validator_id)
        .ok_or_else(|| ApiError::bad_request("validator does not exist"))?;
    if validator.network_id != ctx.network_id || validator.owner_id != ctx.account_id {
        return Err(ApiError::forbidden());
    }
    if !block.committee.iter().any(|m| m.validator_id == validator_id) {
        return Err(ApiError::unprocessable(
            "not_in_committee",
            "validator is not a member of the block committee",
        ));
    }
    endorsement_admission::ensure_can_endorse(state, validator_id, &ctx.network_id)?;
    state.blocks.write().unwrap().add_endorsement(&block.id, validator_id);
    Ok(())
}
