use h1_t3::{apply_uci, GridView, Rights, Sq};
use m2_p5::{Code, Tally};
use crate::pipeline::process_ply;
use std::fs::File;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;

pub fn run_seq(script: &Path, out_path: &Path) -> Result<(), String> {
    let mut grid = GridView::startpos();
    let mut rights = Rights {
        k: true,
        q: true,
        kk: true,
        qq: true,
    };
    let mut ep: Option<Sq> = None;
    let mut stale_ep: Option<Sq> = None;
    let mut tally = Tally::default();
    let mut prev_digest = 0u64;

    let f = File::open(script).map_err(|e| e.to_string())?;
    let reader = BufReader::new(f);
    let mut out = File::create(out_path).map_err(|e| e.to_string())?;
    let mut ply = 0u32;

    for line in reader.lines() {
        let line = line.map_err(|e| e.to_string())?;
        let mv = line.trim();
        if mv.is_empty() || mv.starts_with('#') {
            continue;
        }
        let from_sq = if mv.len() == 4 {
            let f0 = (mv.as_bytes()[0] - b'a') as usize;
            let r0 = (mv.as_bytes()[1] - b'1') as usize;
            r0 * 8 + f0
        } else {
            return Err(format!("illegal move {mv}"));
        };
        let from_piece = grid.cells[from_sq];
        let captured = {
            if mv.len() == 4 {
                let to = ((mv.as_bytes()[3] - b'1') as usize) * 8
                    + (mv.as_bytes()[2] - b'a') as usize;
                grid.cells[to] != b' '
            } else {
                false
            }
        };
        if !apply_uci(&mut grid, &mut rights, &mut ep, mv) {
            return Err(format!("illegal move {mv}"));
        }
        ply += 1;
        let code = process_ply(
            &grid,
            &rights,
            &ep,
            &mut stale_ep,
            &mut tally,
            &mut prev_digest,
            mv,
            from_piece,
            captured,
        );
        let code_s = match code {
            Code::N => "N",
            Code::H => "H",
        };
        let row = format!(
            "{{\"ply\":{ply},\"digest_hex\":\"{:016x}\",\"outcome_code\":\"{code_s}\"}}\n",
            prev_digest
        );
        out.write_all(row.as_bytes()).map_err(|e| e.to_string())?;
    }
    Ok(())
}
