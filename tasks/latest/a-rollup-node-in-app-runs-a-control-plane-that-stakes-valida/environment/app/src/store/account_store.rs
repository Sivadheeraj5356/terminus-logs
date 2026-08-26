use crate::types::account::{Account, AccountStatus};
use std::collections::HashMap;

pub struct AccountStore {
    by_id: HashMap<String, Account>,
}

impl AccountStore {
    pub fn new() -> AccountStore {
        AccountStore {
            by_id: HashMap::new(),
        }
    }

    pub fn insert(&mut self, account: Account) {
        self.by_id.insert(account.id.clone(), account);
    }

    pub fn get_clone(&self, id: &str) -> Option<Account> {
        self.by_id.get(id).cloned()
    }

    pub fn by_username(&self, username: &str) -> Option<Account> {
        self.by_id
            .values()
            .find(|a| a.username == username)
            .cloned()
    }

    pub fn set_status(&mut self, id: &str, status: AccountStatus) -> bool {
        if let Some(account) = self.by_id.get_mut(id) {
            account.status = status;
            true
        } else {
            false
        }
    }

    pub fn credit_balance(&mut self, id: &str, amount: u64) -> bool {
        if let Some(account) = self.by_id.get_mut(id) {
            account.l2_balance = account.l2_balance.saturating_add(amount);
            true
        } else {
            false
        }
    }
}
