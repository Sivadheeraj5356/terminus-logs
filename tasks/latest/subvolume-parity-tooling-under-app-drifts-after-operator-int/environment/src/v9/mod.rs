mod pass_grid;
mod rollup;

use std::path::Path;

use crate::h9::io::{load_lanes, load_reload_seeds, write_report, write_stream};
use crate::n2::store::{
    ensure_var_layout, read_checkpoint, read_journal, read_wrap_gen, write_checkpoint,
    write_journal, write_wrap_gen, Checkpoint,
};
use crate::x7::m8::LaneCache;

pub use pass_grid::pass_lane;
pub use rollup::seal_matrix;

pub fn run_matrix_all(root: &Path) -> Result<(), String> {
    ensure_var_layout(root)?;
    let mut journal = read_journal(root)?;
    let wrap_epoch = read_wrap_gen(root)?;
    let lanes = load_lanes(&root.join("data/lanes"))?;
    let seeds = load_reload_seeds(&root.join("data/reload"))?;

    let mut cache = LaneCache::open(root)?;
    let mut max_lane_epoch = wrap_epoch;

    let rows_by_lane =
        pass_grid::pass_all_lanes(&lanes, &seeds, &mut journal, &mut cache, &mut max_lane_epoch)?;
    let rows: Vec<_> = rows_by_lane.into_values().collect();
    let out = rollup::seal_matrix(rows, &mut journal, max_lane_epoch);

    write_report(&root.join("output/bw_emit.json"), &out.report)?;
    write_stream(
        &root.join("output/stream_sidecar.bin"),
        &out.stream_bytes,
    )?;

    let ckpt = Checkpoint {
        lanes_witnessed: out.report.summary.rows_total,
        last_lane_id: out
            .report
            .rows
            .last()
            .map(|r| r.lane_id.clone())
            .unwrap_or_default(),
    };
    write_checkpoint(root, &ckpt)?;
    write_journal(root, &journal)?;
    write_wrap_gen(root, max_lane_epoch)?;
    let _ = read_checkpoint(root)?;
    Ok(())
}
