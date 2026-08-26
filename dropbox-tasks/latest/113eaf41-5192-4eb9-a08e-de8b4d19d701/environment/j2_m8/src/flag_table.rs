pub mod bind_term_b;
pub mod stub_term;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PhaseTag {
    Active,
    Closed,
    Pending,
}

#[derive(Clone, Debug)]
pub struct SessionCtx {
    pub arm_id: u8,
    pub band_id: u8,
    pub pass_streak: u8,
    pub flags: u16,
    pub cursor: u32,
}

impl SessionCtx {
    pub fn fresh(arm_id: u8, band_id: u8) -> Self {
        Self {
            arm_id,
            band_id,
            pass_streak: 0,
            flags: 0,
            cursor: 0,
        }
    }
}

pub fn shift_lane(session: &mut SessionCtx, lane: u8) {
    session.flags = session.flags.wrapping_add(lane as u16);
    session.cursor = session.cursor.wrapping_add(lane as u32);
}

pub fn gate_cursor(session: &SessionCtx) -> u32 {
    session.cursor ^ (session.flags as u32)
}
