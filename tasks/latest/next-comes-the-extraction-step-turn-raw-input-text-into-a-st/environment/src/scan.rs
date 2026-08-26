use crate::dfa::Dfa;
use crate::parser;

pub struct Compiled {
    pub raw: Vec<u8>,
    pub dfa: Dfa,
    pub anchor_start: bool,
    pub anchor_end: bool,
}

pub fn compile_pattern(raw: &[u8]) -> Result<Compiled, String> {
    let _ = parser::parse(raw)?;
    Err("scan not implemented".to_string())
}

pub fn scan_one(_c: &Compiled, _input: &[u8]) -> Vec<(usize, usize)> {
    Vec::new()
}

pub fn render_report(_items: &[(Vec<u8>, Vec<(usize, usize)>)]) -> String {
    String::new()
}
