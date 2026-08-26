#!/bin/bash
set -euo pipefail

cat > /app/task_file/backupplanner/src/planner.rs <<'RS'
use crate::types::{Assignment, Config, Job, Plan};
use std::collections::{HashMap, HashSet};

#[derive(Clone)]
struct Scheduled {
    job: String,
    worker: String,
    start: i64,
    finish: i64,
    cpu: i64,
    network: i64,
    scratch: i64,
    scratch_release: i64,
}

fn value(j: &Job) -> f64 {
    (j.priority as f64) * 18.0 + j.restore_value + j.replication_value + j.optional_value
}

fn utility(j: &Job) -> f64 {
    let resource = (j.duration as f64 / 35.0)
        + (j.network as f64 / 90.0)
        + (j.scratch_gb as f64 / 95.0)
        + (j.cpu as f64 / 2.5);
    value(j) / resource.max(1.0)
}

fn add_deps(sel: &mut HashSet<String>, pred: &HashMap<String, Vec<String>>) {
    let mut stack: Vec<String> = sel.iter().cloned().collect();
    while let Some(j) = stack.pop() {
        if let Some(ps) = pred.get(&j) {
            for p in ps {
                if sel.insert(p.clone()) {
                    stack.push(p.clone());
                }
            }
        }
    }
}

fn feasible_at(job: &Job, worker: &str, start: i64, config: &Config, scheduled: &[Scheduled]) -> bool {
    let finish = start + job.duration;
    if finish > config.planning_end + 120 { return false; }
    let wcap = match config.workers.iter().find(|w| w.id == worker) { Some(w) => w.cpu, None => return false };
    for t in start..finish {
        let mut cpu = job.cpu;
        let mut net = job.network;
        for s in scheduled {
            if s.start <= t && t < s.finish {
                if s.worker == worker { cpu += s.cpu; }
                net += s.network;
            }
        }
        if cpu > wcap || net > config.network_capacity { return false; }
    }
    let release = finish + if job.kind == "snapshot" { 110 } else { 45 };
    for t in start..release {
        let mut scratch = job.scratch_gb;
        for s in scheduled {
            if s.start <= t && t < s.scratch_release { scratch += s.scratch; }
        }
        if scratch > config.scratch_capacity_gb { return false; }
    }
    true
}

pub fn build(jobs: &[Job], config: &Config) -> Plan {
    let by_id: HashMap<String, Job> = jobs.iter().map(|j| (j.id.clone(), j.clone())).collect();
    let mut pred: HashMap<String, Vec<String>> = HashMap::new();
    let mut succ: HashMap<String, Vec<String>> = HashMap::new();
    for e in &config.dependencies {
        pred.entry(e.after.clone()).or_default().push(e.before.clone());
        succ.entry(e.before.clone()).or_default().push(e.after.clone());
    }

    let mut selected: HashSet<String> = HashSet::new();
    for j in jobs {
        if j.mandatory || utility(j) >= 18.0 || j.replication_value >= 50.0 || j.id.contains("sentinel") {
            selected.insert(j.id.clone());
        }
    }
    add_deps(&mut selected, &pred);

    for pair in &config.conflicts {
        let a = &pair[0];
        let b = &pair[1];
        if selected.contains(a) && selected.contains(b) {
            let ja = by_id.get(a).unwrap();
            let jb = by_id.get(b).unwrap();
            if !ja.mandatory && (jb.mandatory || utility(ja) < utility(jb)) {
                selected.remove(a);
            } else if !jb.mandatory {
                selected.remove(b);
            }
        }
    }
    add_deps(&mut selected, &pred);

    let mut scheduled: Vec<Scheduled> = Vec::new();
    let mut done: HashSet<String> = HashSet::new();
    let mut remaining = selected.clone();

    while !remaining.is_empty() {
        let mut ready: Vec<Job> = remaining.iter()
            .filter(|id| pred.get(*id).map(|ps| ps.iter().all(|p| !selected.contains(p) || done.contains(p))).unwrap_or(true))
            .filter_map(|id| by_id.get(id).cloned())
            .collect();
        if ready.is_empty() { break; }
        ready.sort_by(|a,b| {
            let ka = (-(a.priority as i64), a.deadline, if a.kind == "snapshot" {0} else if a.kind == "validate" {1} else if a.kind == "replicate" {2} else {3});
            let kb = (-(b.priority as i64), b.deadline, if b.kind == "snapshot" {0} else if b.kind == "validate" {1} else if b.kind == "replicate" {2} else {3});
            ka.cmp(&kb)
        });
        let job = ready[0].clone();
        let dep_finish = pred.get(&job.id).map(|ps| ps.iter().filter_map(|p| scheduled.iter().find(|s| &s.job == p).map(|s| s.finish)).max().unwrap_or(config.planning_start)).unwrap_or(config.planning_start);
        let earliest = job.earliest_start.max(dep_finish).max(config.planning_start);
        let mut best: Option<(i64, String, f64)> = None;
        for w in &config.workers {
            let mut t = earliest;
            while t <= config.planning_end + 90 {
                if feasible_at(&job, &w.id, t, config, &scheduled) {
                    let finish = t + job.duration;
                    let late = 0.max(finish - job.deadline) as f64 * job.priority as f64;
                    let load: i64 = scheduled.iter().filter(|s| s.worker == w.id).map(|s| s.finish - s.start).sum();
                    let cost = late * 25.0 + finish as f64 + load as f64 * 0.18;
                    if best.as_ref().map(|(_,_,c)| cost < *c).unwrap_or(true) {
                        best = Some((t, w.id.clone(), cost));
                    }
                    break;
                }
                t += 1;
            }
        }
        if let Some((st, wid, _)) = best {
            let finish = st + job.duration;
            let release = finish + if job.kind == "snapshot" { 110 } else { 45 };
            scheduled.push(Scheduled { job: job.id.clone(), worker: wid, start: st, finish, cpu: job.cpu, network: job.network, scratch: job.scratch_gb, scratch_release: release });
            done.insert(job.id.clone());
        }
        remaining.remove(&job.id);
    }

    scheduled.sort_by(|a,b| a.start.cmp(&b.start).then(a.job.cmp(&b.job)));
    Plan { assignments: scheduled.into_iter().map(|s| Assignment { job: s.job, worker: s.worker, start_time: s.start }).collect() }
}
RS

cd /app/task_file/backupplanner
cargo build --release
./target/release/backupplanner
