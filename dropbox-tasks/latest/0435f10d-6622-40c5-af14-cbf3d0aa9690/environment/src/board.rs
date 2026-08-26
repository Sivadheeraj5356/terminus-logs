use std::collections::BTreeMap;

pub struct Board {
    pub names: Vec<String>,
    pub index: BTreeMap<String, usize>,
    pub adj: Vec<Vec<usize>>,
}

impl Board {
    pub fn parse(_text: &str) -> Result<Board, String> {
        todo!()
    }

    pub fn n(&self) -> usize {
        self.names.len()
    }
}
