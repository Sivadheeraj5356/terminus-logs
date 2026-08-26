mod lane_a;
mod lane_b;
mod lane_c;

use blk_a::SlotView;
use blk_b::CadenceState;
use blk_c::PoolView;
use core_k::{ModeSpec, ObserverSpec, ScenarioSpec};
use lane_a::apply_pack;
use lane_b::apply_cadence;
use lane_c::apply_pool;
use std::collections::HashMap;

fn lit_mask(reach: u32, cx: u32, cy: u32, slots: usize) -> Vec<u8> {
    let mut out = vec![0u8; slots];
    for i in 0..slots {
        let dx = ((i % 4) as i32 - cx as i32).unsigned_abs();
        let dy = ((i / 4) as i32 - cy as i32).unsigned_abs();
        if dx + dy <= reach {
            out[i] = 1;
        }
    }
    out
}

pub struct SimOut {
    pub peak_bytes: u64,
    pub plane_a: Vec<u8>,
    pub plane_b: Vec<u8>,
    pub lineage: Vec<core_k::MergeRow>,
    pub decay_trace: Vec<u32>,
    pub cadence_trace: Vec<String>,
    pub resident_trace: Vec<String>,
    pub plane_trace: Vec<String>,
    pub cadence_trace_v3: Vec<String>,
    pub pool_trace: Vec<String>,
}

fn active_observers<'a>(spec: &'a ScenarioSpec, tick: u64) -> &'a [ObserverSpec] {
    if spec.observer_phases.is_empty() {
        return &spec.observers;
    }
    for phase in &spec.observer_phases {
        if tick <= phase.until_tick {
            return &phase.observers;
        }
    }
    spec.observer_phases
        .last()
        .map(|p| p.observers.as_slice())
        .unwrap_or(&spec.observers)
}

pub fn local_w(spec: &ScenarioSpec, mode: &ModeSpec, ticks: u64) -> SimOut {
    let slots = spec.slots;
    let mut explored = vec![0u8; slots];
    let mut lit = vec![0u8; slots];
    let mut sensor = vec![0u8; slots];
    let mut fade = vec![mode.fade_start; slots];
    let mut peak = mode.cell_bytes * slots as u64 * 2;
    let mut lineage = Vec::new();
    let mut decay_trace = Vec::new();
    let mut cadence_trace = Vec::new();
    let mut resident_trace = Vec::new();
    let mut plane_trace = Vec::new();
    let mut cadence_trace_v3 = Vec::new();
    let mut pool_trace = Vec::new();

    let mut pool = PoolView {
        handles: HashMap::new(),
        allocated_groups: HashMap::new(),
        bytes_used: peak,
        cell_bytes: mode.cell_bytes,
        slots: slots as u64,
        group_header_bytes: mode.group_header_bytes,
        observer_metadata_bytes: mode.observer_metadata_bytes,
    };

    for tick in 0..ticks {
        lit.fill(0);
        sensor.fill(0);
        for obs in active_observers(spec, tick) {
            let mask = lit_mask(obs.reach, obs.cx, obs.cy, slots);
            for (i, m) in mask.iter().enumerate() {
                if *m > 0 {
                    lit[i] = 1;
                    sensor[i] = 1;
                }
            }
        }

        for i in 0..slots {
            if lit[i] > 0 {
                explored[i] = 1;
                fade[i] = mode.fade_start;
            }
        }

        let frozen: Vec<bool> = sensor.iter().map(|&v| v > 0).collect();
        let mut cadence = CadenceState {
            fade_counters: fade.clone(),
            modulus: mode.decay_modulus,
            phase: mode.decay_phase,
        };
        let decay = if mode.decay_modulus > 0 { 1u32 } else { 0u32 };
        let _ = apply_cadence(&mut cadence, tick);
        fade = cadence.fade_counters;

        for i in 0..slots {
            if frozen[i] {
                fade[i] = mode.fade_start;
            }
        }

        for i in 0..slots {
            if explored[i] > 0 && sensor[i] == 0 {
                lit[i] = if fade[i] > 0 { 1 } else { 0 };
            }
        }

        let mut slot = SlotView {
            explored: explored.clone(),
            lit: lit.clone(),
        };
        let _ = apply_pack(&mut slot, &explored, &lit);
        explored = slot.explored;
        lit = slot.lit;

        for (gid, group) in spec.ally_groups.iter().enumerate() {
            if let Ok(copies) = apply_pool(&mut pool, group) {
                if !lineage.iter().any(|row: &core_k::MergeRow| row.group == *group) {
                    lineage.push(core_k::MergeRow {
                        group: group.clone(),
                        handle: group[0],
                        copies,
                    });
                }
                let observers = group
                    .iter()
                    .map(|oid| oid.to_string())
                    .collect::<Vec<String>>()
                    .join(",");
                let handle = pool.handles.get(&group[0]).copied().unwrap_or(group[0]);
                pool_trace.push(format!(
                    "group:{}:observers:{}:handle:{}:copies:{}:bytes:{}",
                    gid, observers, handle, copies, pool.bytes_used
                ));
                peak = peak.max(pool.bytes_used);
            }
        }

        let explored_count = explored.iter().filter(|b| **b > 0).count() as u32;
        let sensor_count = sensor.iter().filter(|b| **b > 0).count() as u32;
        let stale_count = explored_count.saturating_sub(sensor_count);
        let counter_sum: u32 = fade.iter().sum();
        let cadence_entry = format!("tick:{tick}:step:{decay}:sum:{counter_sum}");
        let fade_checksum = core_k::digest16(cadence_entry.as_bytes());

        decay_trace.push(counter_sum);
        cadence_trace.push(cadence_entry.clone());
        resident_trace.push(format!("tick:{tick}:bytes:{}", pool.bytes_used));
        plane_trace.push(format!(
            "tick:{tick}:sensor:{sensor_count}:explored:{explored_count}:stale:{stale_count}"
        ));
        cadence_trace_v3.push(format!(
            "tick:{tick}:decay:{decay}:fade_checksum:{fade_checksum}"
        ));
    }

    SimOut {
        peak_bytes: peak,
        plane_a: explored,
        plane_b: sensor,
        lineage,
        decay_trace: decay_trace.iter().rev().take(8).rev().copied().collect(),
        cadence_trace: cadence_trace.iter().rev().take(12).rev().cloned().collect(),
        resident_trace: resident_trace.iter().rev().take(12).rev().cloned().collect(),
        plane_trace,
        cadence_trace_v3,
        pool_trace,
    }
}

pub fn worker_phases(ticks: u64) -> Vec<String> {
    vec![format!("TICK:{ticks}"), "FLUSH".to_string()]
}
