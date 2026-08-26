use arena::step;
use duel_core::codec::{digest_hex, serialize};
use duel_core::GameState;

pub struct HostRun {
    pub trajectory_digest: String,
    pub final_state: GameState,
}

pub fn run_host(inputs: &[(u8, u8)]) -> HostRun {
    let mut st = GameState::initial();
    let mut buf: Vec<u8> = Vec::new();
    buf.extend_from_slice(&serialize(&st));
    for &(in0, in1) in inputs {
        st = step(&st, in0, in1);
        buf.extend_from_slice(&serialize(&st));
    }
    HostRun {
        trajectory_digest: digest_hex(&buf),
        final_state: st,
    }
}

pub struct ClientRun {
    pub pred_digest: String,
    pub confirmed_digest: String,
    pub rollbacks: u32,
    pub final_state: GameState,
}

pub fn drive_online(_inputs: &[(u8, u8)], _delay: usize) -> ClientRun {
    todo!()
}
