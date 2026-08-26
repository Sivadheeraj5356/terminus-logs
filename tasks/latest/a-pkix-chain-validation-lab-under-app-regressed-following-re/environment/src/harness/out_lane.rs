use crate::hp::t5::apply_pin;
use crate::seg::k4::map_verdict;
use crate::types::{G, RowIn, RowOut, View, Zin};

pub fn consult_only(g: &G, tok: &crate::types::BindToken, z: Zin) -> crate::types::Verdict {
    apply_pin(g, tok, z)
}

pub fn row_only(view: &View, rin: &RowIn) -> RowOut {
    map_verdict(view, rin)
}
