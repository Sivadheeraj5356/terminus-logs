use duel_core::GameState;
use exch::apply_exch;
use lin::apply_lin;

pub fn step(state: &GameState, in0: u8, in1: u8) -> GameState {
    let (np0, np1) = apply_lin(state, in0, in1);
    apply_exch(state, np0, np1, in0, in1)
}
