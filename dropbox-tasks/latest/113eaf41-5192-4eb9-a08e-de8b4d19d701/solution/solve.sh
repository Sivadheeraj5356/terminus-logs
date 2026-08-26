#!/usr/bin/env bash
set -euo pipefail
cd /app/environment

cat > h7_p3/src/fold_play_a.rs <<'RS'
use crate::neighbors;
use crate::{GridState, MoveToken, GRID_H, GRID_W};

pub fn fold_play_a(grid: &mut GridState, mv: MoveToken, arm: u8) -> Result<(), u8> {
    if mv.row >= GRID_H as u8 || mv.col >= GRID_W as u8 {
        return Err(2);
    }
    if grid.get(mv.row, mv.col) != 0 {
        return Err(3);
    }
    let opponent = if mv.side == 1 { 2 } else { 1 };
    match arm {
        0 => {
            for (nr, nc) in neighbors(mv.row, mv.col) {
                if nr < GRID_H as u8 && nc < GRID_W as u8 && grid.get(nr, nc) == opponent {
                    grid.set(nr, nc, 0);
                }
            }
            grid.set(mv.row, mv.col, mv.side);
        }
        1 => {
            if mv.row >= 3 {
                for (nr, nc) in neighbors(mv.row, mv.col) {
                    if nr < GRID_H as u8 && nc < GRID_W as u8 && grid.get(nr, nc) == opponent {
                        grid.set(nr, nc, 0);
                    }
                }
            }
            grid.set(mv.row, mv.col, mv.side);
        }
        2 => {
            if grid.pending > 0 && (mv.flags & 0x0100) == 0 {
                return Err(4);
            }
            if (mv.flags & 0x0100) != 0 {
                grid.pending = 0;
            }
            for (nr, nc) in neighbors(mv.row, mv.col) {
                if nr < GRID_H as u8 && nc < GRID_W as u8 && grid.get(nr, nc) == opponent {
                    grid.set(nr, nc, 0);
                }
            }
            grid.set(mv.row, mv.col, mv.side);
        }
        3 => {
            if mv.col < 6 {
                for (nr, nc) in neighbors(mv.row, mv.col) {
                    if nr < GRID_H as u8 && nc < GRID_W as u8 && grid.get(nr, nc) == opponent {
                        grid.set(nr, nc, 0);
                    }
                }
            }
            grid.set(mv.row, mv.col, mv.side);
        }
        _ => return Err(1),
    }
    grid.seq = grid.seq.saturating_add(1);
    if grid.pending > 0 {
        grid.pending = grid.pending.saturating_sub(1);
    }
    Ok(())
}
RS

cat > j2_m8/src/bind_term_b.rs <<'RS'
use crate::{PhaseTag, SessionCtx};

pub fn bind_term_b(session: &mut SessionCtx, arm_id: u8, flags: u16) -> Result<PhaseTag, u8> {
    let _ = (arm_id, flags);
    session.pass_streak = session.pass_streak.saturating_add(1);
    session.flags |= 0x0001;
    let need = if session.band_id == 0 { 1u8 } else { 2u8 };
    if session.pass_streak >= need {
        session.pass_streak = 0;
        Ok(PhaseTag::Closed)
    } else {
        Ok(PhaseTag::Active)
    }
}
RS

cat > k5_n6/src/eval_repeat_c.rs <<'RS'
use crate::RepeatStore;

pub fn eval_repeat_c(store: &mut RepeatStore, gen: u32) -> Result<(), u8> {
    if let Some(last) = store.journal.back().copied() {
        let hits = store.journal.iter().filter(|&&x| x == last).count();
        if hits >= 2 {
            return Err(7);
        }
    }
    if gen > 0 && gen % 4 == 0 {
        if let Some(last) = store.journal.back().copied() {
            store.journal.retain(|&x| x != last);
        }
    }
    store.generation = store.generation.wrapping_add(1);
    Ok(())
}
RS

bash /app/environment/scripts/bake_rs.sh
/app/environment/bin/grti_matrix_k9 --all-arms --witness-out /app/output/rule_witness.json
