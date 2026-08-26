use crate::types::block::Block;

pub fn collect(block: &Block) -> Vec<String> {
    block.endorsements.clone()
}

pub fn distinct(block: &Block) -> Vec<String> {
    let mut seen: Vec<String> = Vec::new();
    for validator_id in &block.endorsements {
        if !seen.iter().any(|s| s == validator_id) {
            seen.push(validator_id.clone());
        }
    }
    seen
}
