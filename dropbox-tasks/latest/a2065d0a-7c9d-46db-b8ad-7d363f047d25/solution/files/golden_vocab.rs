use crate::model::RawDoc;
use std::collections::BTreeSet;

pub fn build(docs: &[RawDoc]) -> Vec<String> {
    let mut set = BTreeSet::new();
    for doc in docs {
        for token in &doc.tokens {
            set.insert(token.clone());
        }
    }
    set.into_iter().collect()
}
