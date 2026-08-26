use crate::endorsement::roster;
use crate::json::{value, Json};
use crate::types::block::Block;

pub fn summary(block: &Block) -> Json {
    Json::from_pairs(vec![
        ("id", value::s(&block.id)),
        ("parent_hash", value::s(&block.parent_hash)),
        ("height", value::n(block.height as i64)),
        ("total_power", value::n(block.total_power as i64)),
        ("endorser_count", value::n(roster::distinct(block).len() as i64)),
    ])
}
