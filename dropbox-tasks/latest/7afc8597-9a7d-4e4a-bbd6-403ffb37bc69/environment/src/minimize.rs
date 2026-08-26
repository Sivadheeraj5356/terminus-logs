use crate::dfa::Dfa;

pub fn minimize(dfa: &Dfa) -> Dfa {
    Dfa {
        num_states: dfa.num_states,
        start: dfa.start,
        accept: dfa.accept.clone(),
        trans: dfa.trans.clone(),
    }
}
