use bitflags::bitflags;
bitflags! {
    pub struct Flags: u32 {
        const A = 0b01;
        const B = 0b10;
    }
}
pub fn ping() -> u32 {
    cfg_if::cfg_if! {
        if #[cfg(any())] { 0 } else { Flags::A.bits() }
    }
}
