#[derive(Clone, Debug)]
pub enum Node {
    Empty,
    Byte(u8),
    Class(Vec<bool>),
    Concat(Vec<Node>),
    Alt(Vec<Node>),
    Star(Box<Node>),
    Plus(Box<Node>),
    Opt(Box<Node>),
    AnchorStart,
    AnchorEnd,
}
