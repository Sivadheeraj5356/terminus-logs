use crate::digest_stage::digest_for_ply;
use h1_t3::{GridView, Rights, Sq};
use m2_p5::{ledger_mark, op_y7, Code, Tally};

pub fn process_ply(
    grid: &GridView,
    rights: &Rights,
    ep: &Option<Sq>,
    stale_ep: &mut Option<Sq>,
    tally: &mut Tally,
    prev_digest: &mut u64,
    mv: &str,
    _from_piece: u8,
    captured: bool,
) -> Code {
    let curr = digest_for_ply(grid, rights, ep, stale_ep);
    *stale_ep = *ep;
    let _class = ledger_mark(mv, captured);
    let code = op_y7(*prev_digest, curr, rights.mask(), tally);
    *prev_digest = curr;
    code
}
