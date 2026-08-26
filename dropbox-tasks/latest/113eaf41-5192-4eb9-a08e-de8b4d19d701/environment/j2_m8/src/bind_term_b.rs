use crate::{PhaseTag, SessionCtx};

pub fn bind_term_b(session: &mut SessionCtx, arm_id: u8, flags: u16) -> Result<PhaseTag, u8> {
    let _ = (arm_id, flags);
    session.pass_streak = session.pass_streak.saturating_add(1);
    session.flags |= 0x0001;
    Ok(PhaseTag::Active)
}
