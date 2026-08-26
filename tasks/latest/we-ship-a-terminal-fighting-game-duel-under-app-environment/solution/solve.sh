#!/bin/bash
set -euo pipefail
cd /app/environment

cat > lin/src/lib.rs <<'LIN_EOF'
use duel_core::input::{pressed, IN_LEFT, IN_RIGHT};
use duel_core::state::{POS_MAX, POS_MIN};
use duel_core::GameState;

fn step_pos(pos: u8, input: u8) -> u8 {
    let d = if pressed(input, IN_LEFT) && !pressed(input, IN_RIGHT) {
        -1
    } else if pressed(input, IN_RIGHT) && !pressed(input, IN_LEFT) {
        1
    } else {
        0
    };
    (pos as i32 + d).clamp(POS_MIN, POS_MAX) as u8
}

pub fn apply_lin(state: &GameState, in0: u8, in1: u8) -> (u8, u8) {
    let np0 = step_pos(state.p0.pos, in0);
    let np1 = step_pos(state.p1.pos, in1);
    if np0 >= np1 {
        (state.p0.pos, state.p1.pos)
    } else {
        (np0, np1)
    }
}
LIN_EOF

cat > exch/src/lib.rs <<'EXCH_EOF'
use duel_core::input::{pressed, IN_ATTACK, IN_BLOCK, IN_SPECIAL};
use duel_core::{Fighter, GameState};

fn action(atk: u8, meter: u8, opp: u8, dist: i32) -> (u8, i32) {
    if pressed(atk, IN_SPECIAL) && meter >= 10 && dist <= 3 {
        return (25, -10);
    }
    if pressed(atk, IN_ATTACK) && dist <= 1 {
        let dmg = if pressed(opp, IN_BLOCK) { 3 } else { 10 };
        return (dmg, 2);
    }
    (0, 0)
}

fn clamp_meter(meter: u8, delta: i32) -> u8 {
    (meter as i32 + delta).clamp(0, 20) as u8
}

pub fn apply_exch(
    state: &GameState,
    new_pos0: u8,
    new_pos1: u8,
    in0: u8,
    in1: u8,
) -> GameState {
    let dist = new_pos1 as i32 - new_pos0 as i32;
    let (dmg_to_1, dm0) = action(in0, state.p0.meter, in1, dist);
    let (dmg_to_0, dm1) = action(in1, state.p1.meter, in0, dist);
    GameState {
        p0: Fighter {
            pos: new_pos0,
            hp: state.p0.hp.saturating_sub(dmg_to_0),
            meter: clamp_meter(state.p0.meter, dm0),
        },
        p1: Fighter {
            pos: new_pos1,
            hp: state.p1.hp.saturating_sub(dmg_to_1),
            meter: clamp_meter(state.p1.meter, dm1),
        },
    }
}
EXCH_EOF

cat > guess/src/lib.rs <<'GUESS_EOF'
pub fn remote_for_tick(confirmed: i64, k: usize, inputs: &[(u8, u8)]) -> u8 {
    if (k as i64) <= confirmed {
        inputs[k].1
    } else if confirmed >= 0 {
        inputs[confirmed as usize].1
    } else {
        0
    }
}
GUESS_EOF

cat > sess/src/lib.rs <<'SESS_EOF'
use arena::step;
use duel_core::codec::{digest_hex, serialize};
use duel_core::GameState;
use guess::remote_for_tick;

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

pub fn drive_online(inputs: &[(u8, u8)], delay: usize) -> ClientRun {
    let n = inputs.len();
    let init = GameState::initial();
    let mut saved: Vec<GameState> = vec![init; n + 1];
    let mut pred_used: Vec<u8> = vec![0u8; n];
    let mut pred_state: Vec<GameState> = vec![init; n];
    let mut confirmed: i64 = -1;
    let mut rollbacks: u32 = 0;

    let mut receive = |saved: &mut Vec<GameState>,
                       pred_used: &mut Vec<u8>,
                       confirmed: &mut i64,
                       rollbacks: &mut u32,
                       f: usize,
                       upper: usize| {
        let r = f as i64 - delay as i64;
        if r >= 0 && (r as usize) < n && r < f as i64 && r > *confirmed {
            *confirmed = r;
            let ru = r as usize;
            if pred_used[ru] != inputs[ru].1 {
                *rollbacks += 1;
                let mut st = saved[ru];
                for k in ru..upper {
                    let ri = remote_for_tick(*confirmed, k, inputs);
                    pred_used[k] = ri;
                    st = step(&st, inputs[k].0, ri);
                    saved[k + 1] = st;
                }
            }
        }
    };

    for f in 0..n {
        receive(&mut saved, &mut pred_used, &mut confirmed, &mut rollbacks, f, f);
        let ri = remote_for_tick(confirmed, f, inputs);
        pred_used[f] = ri;
        let st = step(&saved[f], inputs[f].0, ri);
        saved[f + 1] = st;
        pred_state[f] = st;
    }
    for f in n..(n + delay) {
        receive(&mut saved, &mut pred_used, &mut confirmed, &mut rollbacks, f, n);
    }

    let mut conf_buf: Vec<u8> = Vec::new();
    conf_buf.extend_from_slice(&serialize(&init));
    for k in 0..n {
        conf_buf.extend_from_slice(&serialize(&saved[k + 1]));
    }
    let mut pred_buf: Vec<u8> = Vec::new();
    pred_buf.extend_from_slice(&serialize(&init));
    for k in 0..n {
        pred_buf.extend_from_slice(&serialize(&pred_state[k]));
    }

    ClientRun {
        pred_digest: digest_hex(&pred_buf),
        confirmed_digest: digest_hex(&conf_buf),
        rollbacks,
        final_state: saved[n],
    }
}
SESS_EOF

bash /app/environment/scripts/build_all.sh

/app/environment/bin/duel --out /app/output/duel_report.json
code=$?
if [[ "$code" -ne 0 ]]; then
  echo "oracle: duel report failed with exit $code" >&2
  exit "$code"
fi

echo "oracle: duel rollback engine complete"
