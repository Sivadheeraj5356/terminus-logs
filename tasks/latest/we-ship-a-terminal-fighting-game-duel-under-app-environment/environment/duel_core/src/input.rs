pub const IN_LEFT: u8 = 1;
pub const IN_RIGHT: u8 = 2;
pub const IN_ATTACK: u8 = 4;
pub const IN_BLOCK: u8 = 8;
pub const IN_SPECIAL: u8 = 16;

pub fn pressed(input: u8, bit: u8) -> bool {
    input & bit != 0
}
