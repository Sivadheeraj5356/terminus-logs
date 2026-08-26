use arena::step;
use duel_core::codec::{digest_hex, serialize};
use duel_core::GameState;

pub fn batch_replay_digest(inputs: &[(u8, u8)]) -> String {
    let mut st = GameState::initial();
    let mut buf: Vec<u8> = Vec::new();
    buf.extend_from_slice(&serialize(&st));
    for &(in0, in1) in inputs {
        st = step(&st, in0, in1);
        buf.extend_from_slice(&serialize(&st));
    }
    digest_hex(&buf)
}
