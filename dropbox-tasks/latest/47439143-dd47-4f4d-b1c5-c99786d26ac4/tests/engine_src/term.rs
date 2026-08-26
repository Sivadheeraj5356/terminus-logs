//! Policy directive terms: a qualifier plus a mechanism. Frozen evidence.

use crate::cidr::Cidr;
use crate::result::SapResult;

pub enum Mech {
    All,
    Ip4(Cidr),
    A(Option<String>),
    Mx(Option<String>),
    Include(String),
}

pub struct Term {
    pub raw: String,
    pub qual: char,
    pub mech: Mech,
}

/// Map a qualifier character to the result it yields when its mechanism matches.
pub fn qualifier_result(q: char) -> SapResult {
    match q {
        '-' => SapResult::Fail,
        '~' => SapResult::SoftFail,
        '?' => SapResult::Neutral,
        _ => SapResult::Pass,
    }
}
