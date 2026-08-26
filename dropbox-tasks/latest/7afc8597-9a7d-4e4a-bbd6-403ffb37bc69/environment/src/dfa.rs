use crate::nfa::Nfa;

pub struct Dfa {
    pub num_states: usize,
    pub start: usize,
    pub accept: Vec<bool>,
    pub trans: Vec<[Option<usize>; 256]>,
}

pub fn subset_construct(_nfa: &Nfa) -> Dfa {
    Dfa {
        num_states: 1,
        start: 0,
        accept: vec![false],
        trans: vec![[None; 256]],
    }
}

pub fn prune_and_canonicalize(dfa: &Dfa) -> Dfa {
    Dfa {
        num_states: dfa.num_states,
        start: dfa.start,
        accept: dfa.accept.clone(),
        trans: dfa.trans.clone(),
    }
}

pub fn render(_dfa: &Dfa) -> String {
    String::new()
}
