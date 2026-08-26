use std::collections::HashMap;

use crate::h9::f2::{chain_stamp, rc_band, stream_tag};
use crate::k3::lane::Lane;
use crate::k3::report::ReportRow;
use crate::n2::store::JournalTail;
use crate::x7::a1::fn_a1;
use crate::x7::g3::{build_graph, fn_g3};
use crate::x7::m8::LaneCache;
use crate::x7::r5::{chain_aligned, fn_r5, import_ok};

pub fn pass_lane(
    lane: &Lane,
    journal: &mut JournalTail,
    cache: &mut LaneCache,
) -> Result<ReportRow, String> {
    if let Some(hit) = cache.get(&lane.lane_id, lane.wrap_epoch) {
        return Ok(hit);
    }

    let source_tail = lane.source_tail();
    let receiver_tail = fn_a1(
        journal,
        &lane.chunk_anchor(),
        lane.interrupted,
        &lane.interrupted_anchor(),
        lane.retry_overwrite,
    );
    let graph = build_graph(&lane.metadata_edges);
    let parent_pick = fn_g3(&graph, &source_tail, &lane.candidate_parents);
    let stamp = chain_stamp(&source_tail, &receiver_tail, &parent_pick);
    let band = rc_band(&source_tail, &receiver_tail, &parent_pick);
    let aligned = chain_aligned(&source_tail, &receiver_tail, &parent_pick);
    let imp = import_ok(lane.content_match);
    let (_replay_ok, sync_label) = fn_r5(imp, aligned, band);

    let row = ReportRow {
        lane_id: lane.lane_id.clone(),
        chain_stamp: stamp,
        parent_pick,
        rc_band: band,
        sync_label: sync_label.to_string(),
        stream_tag: stream_tag(lane),
    };
    cache.put(&lane.lane_id, lane.wrap_epoch, row.clone())?;
    Ok(row)
}

pub fn pass_all_lanes(
    lanes: &[Lane],
    seeds: &[crate::k3::lane::ReloadSeed],
    journal: &mut JournalTail,
    cache: &mut LaneCache,
    max_lane_epoch: &mut u32,
) -> Result<HashMap<String, ReportRow>, String> {
    let mut rows_by_lane: HashMap<String, ReportRow> = HashMap::new();

    for seed in seeds {
        if let Some(base) = lanes.iter().find(|lane| lane.lane_id == seed.lane_id) {
            let mut reloaded = base.clone();
            reloaded.apply_reload(seed);
            *max_lane_epoch = (*max_lane_epoch).max(reloaded.wrap_epoch);
            let row = pass_lane(&reloaded, journal, cache)?;
            rows_by_lane.insert(reloaded.lane_id.clone(), row);
        }
    }

    for lane in lanes {
        *max_lane_epoch = (*max_lane_epoch).max(lane.wrap_epoch);
        let row = pass_lane(lane, journal, cache)?;
        rows_by_lane.insert(lane.lane_id.clone(), row);
    }

    Ok(rows_by_lane)
}
