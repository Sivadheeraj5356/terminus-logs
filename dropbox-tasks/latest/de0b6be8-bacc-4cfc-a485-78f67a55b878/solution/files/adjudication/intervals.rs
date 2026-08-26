use crate::state::model::{Epoch, Obs};
pub fn overlaps(a0: i64, a1: i64, b0: i64, b1: i64) -> bool {
    a0 < b1 && b0 < a1
}
pub fn maintenance(o: &Obs, es: &[Epoch]) -> bool {
    es.iter()
        .any(|e| e.toolcell == o.toolcell && overlaps(o.start, o.end, e.start, e.end))
}
