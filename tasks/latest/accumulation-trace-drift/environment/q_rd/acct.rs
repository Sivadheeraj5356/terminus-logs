use crate::q_rd::AccBuf;

pub fn tally_admits(total_admits: u64, accum_steps: u64, completed_steps: u64) -> i64 {
    (total_admits as i64) - (accum_steps as i64 * completed_steps as i64)
}

pub fn tags_for_step(buf: &AccBuf) -> Vec<u64> {
    buf.tags.clone()
}
