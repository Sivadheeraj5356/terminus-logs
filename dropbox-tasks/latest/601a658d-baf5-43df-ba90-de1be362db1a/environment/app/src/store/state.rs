use crate::audit::audit_log::AuditLog;
use crate::config::policy::PolicyConfig;
use crate::config::secrets::Secrets;
use crate::store::account_store::AccountStore;
use crate::store::active_set_store::ActiveSetStore;
use crate::store::ballot_grant_store::BallotGrantStore;
use crate::store::deposit_store::DepositStore;
use crate::store::gov_delegation_store::GovDelegationStore;
use crate::store::gov_vote_store::GovVoteStore;
use crate::store::network_store::NetworkStore;
use crate::store::block_store::BlockStore;
use crate::store::referendum_store::ReferendumStore;
use crate::store::token_store::TokenStore;
use crate::store::validator_store::ValidatorStore;
use std::sync::RwLock;

pub struct AppState {
    pub networks: RwLock<NetworkStore>,
    pub accounts: RwLock<AccountStore>,
    pub tokens: RwLock<TokenStore>,
    pub validators: RwLock<ValidatorStore>,
    pub active_set: RwLock<ActiveSetStore>,
    pub blocks: RwLock<BlockStore>,
    pub deposits: RwLock<DepositStore>,
    pub referenda: RwLock<ReferendumStore>,
    pub ballot_grants: RwLock<BallotGrantStore>,
    pub gov_delegations: RwLock<GovDelegationStore>,
    pub gov_votes: RwLock<GovVoteStore>,
    pub config: PolicyConfig,
    pub secrets: Secrets,
    pub audit: AuditLog,
}

impl AppState {
    pub fn new(config: PolicyConfig, secrets: Secrets, audit: AuditLog) -> AppState {
        AppState {
            networks: RwLock::new(NetworkStore::new()),
            accounts: RwLock::new(AccountStore::new()),
            tokens: RwLock::new(TokenStore::new()),
            validators: RwLock::new(ValidatorStore::new()),
            active_set: RwLock::new(ActiveSetStore::new()),
            blocks: RwLock::new(BlockStore::new()),
            deposits: RwLock::new(DepositStore::new()),
            referenda: RwLock::new(ReferendumStore::new()),
            ballot_grants: RwLock::new(BallotGrantStore::new()),
            gov_delegations: RwLock::new(GovDelegationStore::new()),
            gov_votes: RwLock::new(GovVoteStore::new()),
            config,
            secrets,
            audit,
        }
    }
}
