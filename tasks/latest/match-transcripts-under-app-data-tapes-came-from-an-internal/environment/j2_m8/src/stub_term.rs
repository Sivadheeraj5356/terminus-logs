use crate::{PhaseTag, SessionCtx};

pub fn stub_term(_session: &mut SessionCtx) -> PhaseTag {
    PhaseTag::Pending
}
