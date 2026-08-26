use super::canonical;
use crate::auth::context::AuthContext;
use crate::crypto::{signature, tokens};
use crate::types::clock;
use crate::types::ids;
use crate::types::validator::{Validator, ValidatorStatus};

pub fn build(
    ctx: &AuthContext,
    name: &str,
    stake: u64,
    attested: bool,
    attest_key: &str,
) -> Validator {
    let mut validator = Validator {
        id: ids::new_id("val"),
        network_id: ctx.network_id.clone(),
        owner_id: ctx.account_id.clone(),
        name: name.to_string(),
        stake,
        effective_power: stake,
        status: ValidatorStatus::Registered,
        attested,
        attestation: String::new(),
        signing_key: tokens::mint_secret(),
        session_credential: String::new(),
        created_at: clock::now_secs(),
    };
    if attested {
        let message = canonical::identity(&validator);
        validator.attestation = signature::sign(attest_key, &message);
    }
    validator
}
