#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Code {
    N,
    H,
}

#[derive(Clone, Debug, Default)]
pub struct Tally {
    pub last: [u64; 2],
    pub count: u8,
    pub global: std::collections::HashMap<u64, u8>,
    pub first_rights: std::collections::HashMap<u64, u8>,
}

pub fn op_y7(prev: u64, curr: u64, rights_mask: u8, tally: &mut Tally) -> Code {
    let _ = prev;
    if tally.last[0] == curr || tally.last[1] == curr {
        tally.count = tally.count.saturating_add(1);
    } else {
        tally.count = 1;
    }
    tally.last[0] = tally.last[1];
    tally.last[1] = curr;
    tally.first_rights.entry(curr).or_insert(rights_mask);
    let first = *tally.first_rights.get(&curr).unwrap_or(&rights_mask);
    let g = tally.global.entry(curr).or_insert(0);
    *g = g.saturating_add(1);
    let gc = *g;
    if gc >= 3 && tally.count < 3 && first != rights_mask {
        Code::H
    } else if tally.count >= 3 {
        Code::H
    } else {
        Code::N
    }
}
