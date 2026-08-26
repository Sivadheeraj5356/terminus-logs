use crate::ast::Node;

#[derive(Clone)]
pub struct State {
    pub eps: Vec<usize>,
    pub trans: Vec<(Vec<bool>, usize)>,
}

pub struct Nfa {
    pub states: Vec<State>,
    pub start: usize,
    pub accept: usize,
}

pub fn build(_node: &Node) -> Nfa {
    Nfa {
        states: vec![State {
            eps: Vec::new(),
            trans: Vec::new(),
        }],
        start: 0,
        accept: 0,
    }
}
