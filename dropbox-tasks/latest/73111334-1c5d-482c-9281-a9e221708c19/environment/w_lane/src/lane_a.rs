use blk_a::pack_a;
use blk_a::{PackErr, SlotView};

pub fn apply_pack(slot: &mut SlotView, explored: &[u8], lit: &[u8]) -> Result<u32, PackErr> {
    pack_a(slot, explored, lit)
}
