use crate::types::account::ApiToken;
use std::collections::HashMap;

pub struct TokenStore {
    by_fingerprint: HashMap<String, ApiToken>,
}

impl TokenStore {
    pub fn new() -> TokenStore {
        TokenStore {
            by_fingerprint: HashMap::new(),
        }
    }

    pub fn insert(&mut self, token: ApiToken) {
        self.by_fingerprint.insert(token.fingerprint.clone(), token);
    }

    pub fn find_by_fingerprint(&self, fingerprint: &str) -> Option<&ApiToken> {
        self.by_fingerprint.get(fingerprint)
    }
}
