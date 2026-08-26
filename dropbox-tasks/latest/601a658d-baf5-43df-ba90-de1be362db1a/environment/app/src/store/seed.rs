use crate::crypto::{hashing, rng};
use crate::store::state::AppState;
use crate::types::account::{Account, AccountStatus, Role};
use crate::types::network::Network;

pub fn seed(state: &AppState) {
    seed_networks(state);
    seed_accounts(state);
}

fn seed_networks(state: &AppState) {
    let mut networks = state.networks.write().unwrap();
    networks.insert(Network {
        id: "network-alpha".to_string(),
        name: "Alpha Mainnet".to_string(),
        region: "us-east".to_string(),
    });
    networks.insert(Network {
        id: "network-beta".to_string(),
        name: "Beta Testnet".to_string(),
        region: "us-east".to_string(),
    });
    networks.insert(Network {
        id: "network-ops".to_string(),
        name: "Operations Subnet".to_string(),
        region: "us-west".to_string(),
    });
}

fn seed_accounts(state: &AppState) {
    seed_account(state, "acct-alice", "network-alpha", "alice", "alice-pw-9f3", Role::Participant);
    seed_account(state, "acct-carol", "network-alpha", "carol", "carol-pw-7c2", Role::Participant);
    seed_account(state, "acct-dave", "network-alpha", "dave", "dave-pw-2k9", Role::Participant);
    seed_account(state, "acct-erin", "network-alpha", "erin", "erin-pw-6m4", Role::Operator);
    seed_account(state, "acct-bob", "network-beta", "bob", "bob-pw-4a1", Role::Participant);
    seed_account(state, "acct-ops", "network-ops", "opsuser", "ops-pw-3d7", Role::Operator);
    seed_account(state, "acct-root", "network-ops", "root", "root-pw-1b8", Role::Admin);
}

fn seed_account(
    state: &AppState,
    id: &str,
    network_id: &str,
    username: &str,
    password: &str,
    role: Role,
) {
    let salt = rng::token_hex(8);
    let password_hash = hashing::hash_password(password, &salt);
    let mut accounts = state.accounts.write().unwrap();
    accounts.insert(Account {
        id: id.to_string(),
        network_id: network_id.to_string(),
        username: username.to_string(),
        password_salt: salt,
        password_hash,
        role,
        status: AccountStatus::Active,
        l2_balance: 0,
    });
}
