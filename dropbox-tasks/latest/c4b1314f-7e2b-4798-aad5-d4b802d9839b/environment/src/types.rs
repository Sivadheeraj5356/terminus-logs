pub struct Ctx {
    pub acc: u64,
}

pub struct S {
    pub last_carry: u64,
}

pub struct BindToken {
    pub carry: u64,
}

pub struct G {
    pub slice: [u8; 4],
}

pub struct Zin {
    pub key: u32,
}

pub struct Verdict {
    pub latch_denied: bool,
}

pub struct View {
    pub pulled: bool,
}

pub struct RowIn {
    pub tag_code: u32,
    pub text_a: bool,
    pub text_b: bool,
}

pub struct RowOut {
    pub tag_code: u32,
    pub latch_denied: bool,
}

impl Ctx {
    pub fn new() -> Self {
        Self { acc: 0 }
    }
}

impl S {
    pub fn new(seed: u64) -> Self {
        Self { last_carry: seed }
    }
}

impl G {
    pub fn unit() -> Self {
        Self { slice: [1, 0, 2, 3] }
    }
}
