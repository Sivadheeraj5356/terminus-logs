use crate::endorsement::roster;
use crate::types::block::Block;

pub fn effective_endorsers(block: &Block) -> Vec<String> {
    roster::distinct(block)
}
