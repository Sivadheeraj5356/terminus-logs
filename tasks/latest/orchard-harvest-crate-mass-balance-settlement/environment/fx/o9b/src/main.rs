use std::collections::HashMap;
use std::env;
use std::path::PathBuf;

use o0m::{BalanceReport, ReplayCheckpoint, SCHEMA_GENERATION};
use o1p::load_feed;
use o3z::ZoneTracker;
use o4b::seal_balance;
use o5r::{layout_zones, write_report};
use o6t::TareRegistry;
use o7x::{
    baseline_kept_ids, settle_picks, settle_spoilage_winners, settle_supersede_winners,
    spoilage_lineage, supersede_lineage,
};
use o8w::{input_identity, load_checkpoint, wal_identity_accept, write_checkpoint};

fn main() {
    if let Err(msg) = run() {
        eprintln!("pick-balance: {msg}");
        std::process::exit(1);
    }
}

fn zone_order_from_picks(feed: &o0m::InputFeed) -> Vec<String> {
    let mut sorted = feed.picks.clone();
    sorted.sort_by(|a, b| a.sequence.cmp(&b.sequence));
    let mut order = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for row in sorted {
        if seen.insert(row.zone.clone()) {
            order.push(row.zone);
        }
    }
    order
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let mut input = PathBuf::from("/app/data/feed.jsonl");
    let mut out = PathBuf::from("/app/output/pick_report.json");
    let mut checkpoint_in: Option<PathBuf> = None;
    let mut checkpoint_out: Option<PathBuf> = None;
    while let Some(flag) = args.next() {
        match flag.as_str() {
            "--input" => input = args.next().ok_or("missing --input")?.into(),
            "--out" => out = args.next().ok_or("missing --out")?.into(),
            "--checkpoint-in" => {
                checkpoint_in = Some(args.next().ok_or("missing --checkpoint-in")?.into())
            }
            "--checkpoint-out" => {
                checkpoint_out = Some(args.next().ok_or("missing --checkpoint-out")?.into())
            }
            other => return Err(format!("unknown flag {other}")),
        }
    }

    let identity = input_identity(&input)?;
    let feed = load_feed(&input)?;
    let registry = TareRegistry::ingest(&feed.tares);
    let tare_lineage = registry.lineage();
    let baseline = baseline_kept_ids(&feed.picks, &registry);
    let supersede_winners = settle_supersede_winners(&feed.supersedes, &baseline);
    let spoilage_winners = settle_spoilage_winners(&feed.spoilages, &baseline);
    let supersede_lin = supersede_lineage(&feed.supersedes, &supersede_winners);
    let spoilage_lin = spoilage_lineage(&feed.spoilages, &spoilage_winners);
    let settled = settle_picks(
        &feed.picks,
        &supersede_winners,
        &spoilage_winners,
        &registry,
    );
    let order = zone_order_from_picks(&feed);

    let mut tracker = ZoneTracker::default();
    let mut resumed = false;
    if let Some(ckpt_path) = checkpoint_in {
        if let Ok(ckpt) = load_checkpoint(&ckpt_path) {
            if wal_identity_accept(
                &ckpt,
                &identity,
                &tare_lineage,
                &supersede_winners,
                &spoilage_winners,
            ) {
                for zone in &ckpt.zone_order {
                    if let Some(state) = ckpt.zone_states.get(zone) {
                        tracker.import_checkpoint(zone, state.clone());
                    }
                }
                resumed = true;
            }
        }
    }
    if !resumed {
        tracker.replay_settled(&settled);
    }

    let zones = layout_zones(tracker.snapshot());
    let stamp_parts: Vec<String> = zones
        .iter()
        .flat_map(|z| z.pick_marks.clone())
        .collect();
    let report = BalanceReport {
        zones,
        balance_stamp: seal_balance(
            &stamp_parts,
            &tare_lineage,
            &supersede_lin,
            &spoilage_lin,
        ),
    };
    write_report(&out, &report)?;

    if let Some(ckpt_out) = checkpoint_out {
        let last_pos = feed.events.last().map(|e| e.position).unwrap_or(0);
        let mut zone_states = HashMap::new();
        for zone in &order {
            if let Some(state) = tracker.export_checkpoint(zone) {
                zone_states.insert(zone.clone(), state);
            }
        }
        let ckpt = ReplayCheckpoint {
            input_identity: identity,
            schema_generation: SCHEMA_GENERATION,
            last_event_position: last_pos,
            tare_lineage: tare_lineage.clone(),
            zone_order: order,
            zone_states,
            supersede_winners,
            spoilage_winners,
            previous_stamp_seed: report.balance_stamp.clone(),
        };
        write_checkpoint(&ckpt_out, &ckpt)?;
    }

    Ok(())
}
