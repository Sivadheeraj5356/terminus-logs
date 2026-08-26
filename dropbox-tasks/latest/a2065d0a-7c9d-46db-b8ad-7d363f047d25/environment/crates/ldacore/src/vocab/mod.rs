use crate::model::RawDoc;
use std::collections::HashSet;

pub fn build(docs: &[RawDoc]) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut order = Vec::new();
    for doc in docs {
        for token in &doc.tokens {
            if seen.insert(token.clone()) {
                order.push(token.clone());
            }
        }
    }
    order
}
