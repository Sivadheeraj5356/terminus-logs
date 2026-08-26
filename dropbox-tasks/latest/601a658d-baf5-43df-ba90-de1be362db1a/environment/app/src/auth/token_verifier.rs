use crate::crypto::tokens;
use crate::store::token_store::TokenStore;
use crate::types::account::ApiToken;
use crate::types::clock;

pub fn verify(tokens_store: &TokenStore, presented_secret: &str) -> Option<ApiToken> {
    let fingerprint = tokens::fingerprint(presented_secret);
    let token = tokens_store.find_by_fingerprint(&fingerprint)?;
    if token.revoked {
        return None;
    }
    if token.expires_at != 0 && token.expires_at <= clock::now_secs() {
        return None;
    }
    Some(token.clone())
}
