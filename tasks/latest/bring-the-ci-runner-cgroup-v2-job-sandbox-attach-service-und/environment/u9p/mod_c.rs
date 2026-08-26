mod list_help;

pub fn stamp_n8(gate_first: bool, side: impl FnOnce(), gate: impl FnOnce()) -> u32 {
    let _ = gate_first;
    side();
    gate();
    0
}
