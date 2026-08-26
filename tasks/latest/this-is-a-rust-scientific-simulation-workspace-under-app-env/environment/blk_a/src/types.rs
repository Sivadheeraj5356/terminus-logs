pub struct SlotView {
    pub explored: Vec<u8>,
    pub lit: Vec<u8>,
}

#[derive(Debug)]
pub enum PackErr {
    SizeMismatch,
}
