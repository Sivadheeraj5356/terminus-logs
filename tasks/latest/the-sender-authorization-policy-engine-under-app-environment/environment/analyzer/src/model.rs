//! Shapes the analyzer works with. Provided by the scaffold.

use std::collections::HashMap;

pub struct Rec {
    pub sap: Option<String>,
    pub a: Vec<String>,
    pub mx: Vec<String>,
}

pub struct Zone {
    pub map: HashMap<String, Rec>,
}

impl Zone {
    pub fn get(&self, domain: &str) -> Option<&Rec> {
        self.map.get(domain)
    }
}

/// One authorization question: is `ip` allowed to send mail for `domain`?
pub struct Query {
    pub id: String,
    pub domain: String,
    pub ip: u32,
}

pub enum Mech {
    All,
    /// An `ip4` block as written: the network address and the prefix length
    /// exactly as they appeared in the policy.
    Ip4 { net: u32, prefix: u8 },
    A(Option<String>),
    Mx(Option<String>),
    Include(String),
}

pub struct Term {
    /// The directive exactly as it appeared in the policy string.
    pub raw: String,
    pub qual: char,
    pub mech: Mech,
}

pub struct Policy {
    pub directives: Vec<Term>,
    pub redirect: Option<String>,
    pub has_all: bool,
}

/// What the analyzer reports for one query.
pub struct Cert {
    pub id: String,
    pub deployed: String,
    pub intended: String,
    pub divergent: bool,
    pub witness: Option<String>,
}
