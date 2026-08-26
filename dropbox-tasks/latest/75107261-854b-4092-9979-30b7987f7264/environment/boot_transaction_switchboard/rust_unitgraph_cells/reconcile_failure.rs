//! Stable nonzero exit families.
pub const EXIT_INVOCATION: i32 = 2;
pub const EXIT_YARD_CUSTODY: i32 = 3;
pub const EXIT_ORDER_GRAMMAR: i32 = 4;
pub const EXIT_UNIT_LOADING: i32 = 5;
pub const EXIT_INSTALL_POLICY: i32 = 6;
pub const EXIT_DEPENDENCY_TX: i32 = 7;
pub const EXIT_BOOT_SIM: i32 = 8;
pub const EXIT_MUTATION: i32 = 9;
pub const EXIT_CLOSURE: i32 = 10;

#[derive(Clone, Debug)]
pub struct Fail {
    pub code: i32,
    pub msg: String,
}

impl Fail {
    pub fn new(code: i32, msg: impl Into<String>) -> Self {
        Self { code, msg: msg.into() }
    }
}
