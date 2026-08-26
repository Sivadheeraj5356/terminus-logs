pub const PRESERVE: u32 = 0x8000_0000;

pub fn record_allowed(action_mask: u32, sweep_mask: u32) -> bool {
    action_mask == sweep_mask
}
