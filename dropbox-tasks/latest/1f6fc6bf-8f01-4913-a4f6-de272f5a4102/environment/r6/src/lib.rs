use prlg_a2::journal_digest;
use prlg_c8::{Policy, ShardEndpoint};
use prlg_i1::{load as load_workload, Workload};
use prlg_k4::{ReclaimRow, Store};
use prlg_l7::LingerPlane;
use prlg_p3::{ping, Pool};
use prlg_w5::{RunReport, TraceEvent};
use std::collections::HashMap;
use std::path::Path;
use std::thread;
use std::time::Duration;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum RunError {
    #[error("policy: {0}")]
    Policy(#[from] prlg_c8::PolicyError),
    #[error("workload: {0}")]
    Workload(#[from] prlg_i1::WorkloadError),
    #[error("store: {0}")]
    Store(#[from] prlg_k4::StoreError),
    #[error("pool: {0}")]
    Pool(#[from] prlg_p3::PoolError),
    #[error("spawn: {0}")]
    Spawn(#[from] std::io::Error),
    #[error("export: {0}")]
    Export(#[from] prlg_w5::ExportError),
    #[error("workload mismatch")]
    WorkloadMismatch,
    #[error("descriptor budget exceeded")]
    DescriptorBudget,
    #[error("generation effective limit exceeded")]
    EffectiveLimit,
    #[error("governance not ready")]
    GovernanceNotReady,
    #[error("invalid phase")]
    BadPhase,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Phase {
    Populate,
    Idle,
    Verify,
    All,
}

impl Phase {
    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "populate" => Some(Self::Populate),
            "idle" => Some(Self::Idle),
            "verify" => Some(Self::Verify),
            "all" => Some(Self::All),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct RunOpts {
    pub seed: u64,
    pub phase: Phase,
    pub workload_rounds: Option<u32>,
}

pub struct RunOutput {
    pub report: RunReport,
    pub reclaims: Vec<ReclaimRow>,
    pub trace: Vec<TraceEvent>,
    pub require_full: bool,
}

pub fn gate_g(store: &Store, phase: Phase) -> Result<(), RunError> {
    if phase == Phase::Idle && !store.governance_ready()? {
        return Err(RunError::GovernanceNotReady);
    }
    Ok(())
}

pub fn drive(
    policy: &Policy,
    workload: &Workload,
    shards: &[ShardEndpoint],
    store: &mut Store,
    state_path: &Path,
    opts: RunOpts,
) -> Result<RunOutput, RunError> {
    let (_gen, _ready) = match store.begin_run(&workload.workload_id) {
        Ok(v) => v,
        Err(prlg_k4::StoreError::WorkloadMismatch) => return Err(RunError::WorkloadMismatch),
        Err(e) => return Err(e.into()),
    };

    let mut pool = Pool::new();
    let mut linger = LingerPlane::new();
    let mut trace: Vec<TraceEvent> = Vec::new();
    let mut checkouts_total = 0u32;
    let shard_map: HashMap<u32, ShardEndpoint> = shards.iter().map(|s| (s.id, s.clone())).collect();
    let round_limit = opts.workload_rounds.unwrap_or(workload.rounds.len() as u32);
    let pool_gen = store.pool_generation()?;

    if opts.phase == Phase::Idle {
        gate_g(store, Phase::Idle)?;
    }

    if opts.phase == Phase::Populate || opts.phase == Phase::All {
        step_1(
            policy,
            workload,
            &shard_map,
            &mut pool,
            &mut trace,
            &mut checkouts_total,
            pool_gen,
            round_limit,
            opts.seed,
        )?;
        store.mark_populated()?;
    }

    if opts.phase == Phase::Idle || opts.phase == Phase::All {
        phase_b(policy, store, &mut pool, &mut linger, &mut trace, pool_gen)?;
    }

    let reclaims = store.list_reclaims()?;
    let digest = journal_digest(&reclaims);
    let pool_peak = pool.peak();
    let state_bytes = store.state_bytes(state_path);
    let round_count = workload.rounds.len() as u32;
    let require_full = opts.workload_rounds.is_none()
        && (opts.phase == Phase::All || opts.phase == Phase::Verify);

    let report = RunReport {
        schema_version: 1,
        workload_id: workload.workload_id.clone(),
        round_count,
        pool_generation: store.pool_generation()?,
        checkouts_total,
        reclaims_total: reclaims.len() as u32,
        journal_digest: digest,
        pool_peak,
        state_bytes,
    };

    Ok(RunOutput {
        report,
        reclaims,
        trace,
        require_full,
    })
}

fn step_1(
    policy: &Policy,
    workload: &Workload,
    shards: &HashMap<u32, ShardEndpoint>,
    pool: &mut Pool,
    trace: &mut Vec<TraceEvent>,
    checkouts: &mut u32,
    pool_gen: u32,
    round_limit: u32,
    _seed: u64,
) -> Result<(), RunError> {
    for round in workload.rounds.iter().take(round_limit as usize) {
        let shard = shards.get(&round.shard).ok_or_else(|| {
            prlg_p3::PoolError::Io(std::io::Error::new(std::io::ErrorKind::NotFound, "shard"))
        })?;
        let checked = pool.checkout(shard, policy.pool_max_per_shard, policy.descriptor_ceiling)?;
        *checkouts += 1;
        trace.push(TraceEvent {
            socket_id: checked.socket_id,
            phase: "checkout".into(),
            pool_generation: pool_gen,
            shard: round.shard,
        });
        if round.op == "ping" {
            let mut stream = checked.stream.try_clone().map_err(RunError::Spawn)?;
            ping(&mut stream)?;
            trace.push(TraceEvent {
                socket_id: checked.socket_id,
                phase: "pong".into(),
                pool_generation: pool_gen,
                shard: round.shard,
            });
        }
        pool.checkin(checked.socket_id)?;
        trace.push(TraceEvent {
            socket_id: checked.socket_id,
            phase: "checkin".into(),
            pool_generation: pool_gen,
            shard: round.shard,
        });
    }
    if pool.resolve_c() > policy.descriptor_ceiling {
        return Err(RunError::DescriptorBudget);
    }
    Ok(())
}

fn phase_b(
    policy: &Policy,
    store: &mut Store,
    pool: &mut Pool,
    linger: &mut LingerPlane,
    trace: &mut Vec<TraceEvent>,
    pool_gen: u32,
) -> Result<(), RunError> {
    thread::sleep(Duration::from_millis(
        policy.populate_sleep_ms as u64 + policy.idle_close_ms as u64,
    ));
    let fds = pool.active_fds();
    let dead = linger.op_a(&fds);
    linger.reconcile_b(&dead);
    for sid in dead {
        if let Some(item) = pool.remove_socket(sid) {
            let row = ReclaimRow {
                socket_id: sid,
                shard: item.shard,
                event: "linger_reclaim".into(),
                pool_generation: pool_gen,
                round_index: u32::MAX,
            };
            store.persist_d(&row)?;
            trace.push(TraceEvent {
                socket_id: sid,
                phase: "reclaim".into(),
                pool_generation: pool_gen,
                shard: item.shard,
            });
        }
    }
    Ok(())
}

pub fn load_policy(path: &str) -> Result<Policy, RunError> {
    Ok(prlg_c8::load(path)?)
}

pub fn load_workload_file(path: &str) -> Result<Workload, RunError> {
    Ok(load_workload(path)?)
}

pub fn resolve_shards(policy: &Policy, profile: &str) -> Result<Vec<ShardEndpoint>, RunError> {
    Ok(prlg_c8::resolve_profile(policy, profile)?)
}
