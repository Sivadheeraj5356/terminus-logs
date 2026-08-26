//! The differential decision — SCAFFOLD, implement this.
//!
//! `analyze_query` receives the parsed `Zone` (see `model.rs`) and one `Query`,
//! and must return:
//!
//!   (deployed, intended, divergent, witness)
//!
//! where `deployed` is the result the frozen engine under `../engine` actually
//! produces for this query, `intended` is the result `docs/sap-spec.md` Part 1
//! requires, each being one of PASS / FAIL / SOFTFAIL / NEUTRAL / NONE /
//! PERMERROR; `divergent` is their inequality; and `witness` is `Some(token)`
//! for a divergent query and `None` otherwise. Which token, and which side it is
//! drawn from, is Part 2 of the specification.
//!
//! `parse::parse_policy` turns a record's `sap` string into a `Policy` for you.
//! Both results are yours to compute: the specification gives you one of them,
//! the engine's sources are the only account of the other.
//!
//! The stub below is intentionally incomplete: it reports every query as NONE
//! and never finds a divergence.

use crate::model::{Query, Zone};

pub fn analyze_query(_zone: &Zone, _q: &Query) -> (String, String, bool, Option<String>) {
    ("NONE".to_string(), "NONE".to_string(), false, None)
}
