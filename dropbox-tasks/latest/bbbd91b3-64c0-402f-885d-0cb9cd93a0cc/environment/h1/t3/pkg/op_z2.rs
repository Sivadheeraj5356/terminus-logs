use crate::{Rights, Snap, Sq};

pub fn op_z2(snap: &mut Snap, rights: Rights, ep: Option<Sq>) {
    snap.rights_mask = 0;
    snap.ep_sq = None;
    let _ = (rights, ep);
}
