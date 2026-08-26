use crate::adjudication::intervals;
use crate::state::model::{Obs, Policy};
pub fn apply(o: &mut Obs, p: &Policy) {
    o.effective = if intervals::maintenance(o, &p.epochs) {
        o.reliability * 4 / 5
    } else {
        o.reliability
    };
    o.eligible = o.effective >= p.minimum;
}
