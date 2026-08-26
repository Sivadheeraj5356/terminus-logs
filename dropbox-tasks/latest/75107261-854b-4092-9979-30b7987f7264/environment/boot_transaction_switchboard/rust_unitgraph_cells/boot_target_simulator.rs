//! Cold boot job simulation.
use std::collections::{BTreeMap, BTreeSet};

use crate::boot_semantics::Semantics;
use crate::condition_evaluator::{self, PredResult};
use crate::device_alias_resolver;
use crate::fragment_locator::EffectiveUnit;
use crate::job_state_machine::{self, State};
use crate::order_reader::Order;
use crate::transaction_builder::Transaction;
use crate::unit_parser;
use crate::yard_inventory::Yard;

#[derive(Clone, Debug)]
pub struct SimResult {
    pub states: BTreeMap<String, job_state_machine::JobState>,
    pub events: Vec<String>,
}

pub fn simulate(
    tx: &Transaction,
    effective: &BTreeMap<String, EffectiveUnit>,
    yard: &Yard,
    order: &Order,
    sem: &Semantics,
) -> Result<SimResult, i32> {
    let settle = sem.decide_or("JOB_SETTLE", &["mode"], "immediate");
    let automount_mode = sem.decide_or("AUTOMOUNT_TRIGGER", &["start_automount"], "start_mount");
    let mut states = job_state_machine::new_map(tx.jobs.keys().cloned());
    let mut events = Vec::new();
    let active: BTreeSet<String> = yard.initial_active.iter().cloned().collect();
    let triggers: BTreeSet<String> = order.access_triggers.iter().cloned().collect();

    let mut order_units: Vec<String> = tx.jobs.keys().cloned().collect();
    order_units.sort();
    if settle == "after_stops_preds" {
        for u in order_units.clone() {
            if tx.jobs.get(&u).map(|j| j.kind == "stop").unwrap_or(false) {
                let st = states.get_mut(&u).unwrap();
                st.state = State::Stopped;
                st.reason = "conflict-stop".into();
                events.push(format!("stop\t{}\tconflict-stop", u));
            }
        }
    }

    for _round in 0..64 {
        let mut progress = false;
        for u in order_units.clone() {
            let job_kind = tx.jobs.get(&u).map(|j| j.kind.clone()).unwrap_or_else(|| "start".into());
            if job_kind == "stop" {
                if settle == "immediate" {
                    let st = states.get_mut(&u).unwrap();
                    if st.state == State::Queued {
                        st.state = State::Stopped;
                        st.reason = "conflict-stop".into();
                        events.push(format!("stop\t{}\tconflict-stop", u));
                        progress = true;
                    }
                }
                continue;
            }
            let cur = states.get(&u).unwrap().state.clone();
            if matches!(cur, State::Started | State::Skipped | State::Failed | State::Excluded | State::Stopped) {
                continue;
            }
            let Some(eu) = effective.get(&u) else {
                let st = states.get_mut(&u).unwrap();
                st.state = State::Excluded;
                st.reason = "missing".into();
                progress = true;
                continue;
            };
            if eu.masked {
                let st = states.get_mut(&u).unwrap();
                st.state = State::Failed;
                st.reason = "masked".into();
                events.push(format!("fail\t{}\tmasked", u));
                progress = true;
                continue;
            }
            match condition_evaluator::evaluate(eu, yard, sem) {
                PredResult::Skip => {
                    let st = states.get_mut(&u).unwrap();
                    st.state = State::Skipped;
                    st.reason = "condition-failed".into();
                    events.push(format!("skip\t{}\tcondition-failed", u));
                    progress = true;
                    continue;
                }
                PredResult::Fail => {
                    let st = states.get_mut(&u).unwrap();
                    st.state = State::Failed;
                    st.reason = "assert-failed".into();
                    events.push(format!("fail\t{}\tassert-failed", u));
                    progress = true;
                    continue;
                }
                PredResult::Ok => {}
            }
            let mut waiting = false;
            for e in tx.edges.iter().filter(|e| e.from == u && e.kind == "after") {
                if let Some(ps) = states.get(&e.to) {
                    if !matches!(ps.state, State::Started | State::Skipped | State::Stopped | State::Excluded) {
                        waiting = true;
                    }
                }
            }
            if waiting {
                let st = states.get_mut(&u).unwrap();
                if st.state != State::Waiting {
                    st.state = State::Waiting;
                    progress = true;
                }
                continue;
            }
            let mut dep_fail = false;
            for e in tx.edges.iter().filter(|e| e.from == u) {
                match e.kind.as_str() {
                    "requires" | "bindsto" => {
                        if let Some(ps) = states.get(&e.to) {
                            if ps.state == State::Failed {
                                let prop = sem.decide_or("REQUIRES_FAILURE", &["Requires", "peer_failed"], "owner_ok");
                                if prop == "owner_fail" { dep_fail = true; }
                            }
                        }
                    }
                    "wants" => {
                        if let Some(ps) = states.get(&e.to) {
                            if ps.state == State::Failed {
                                let prop = sem.decide_or("WANTS_FAILURE", &["Wants", "peer_failed"], "owner_fail");
                                if prop == "owner_fail" { dep_fail = true; }
                            }
                        }
                    }
                    "requisite" => {
                        if !active.contains(&e.to) {
                            let st = states.get_mut(&u).unwrap();
                            st.state = State::Failed;
                            st.reason = "requisite-inactive".into();
                            events.push(format!("fail\t{}\trequisite-inactive", u));
                            progress = true;
                            dep_fail = true;
                        }
                    }
                    _ => {}
                }
            }
            if dep_fail {
                if states.get(&u).unwrap().state != State::Failed {
                    let st = states.get_mut(&u).unwrap();
                    st.state = State::Failed;
                    st.reason = "dependency-failed".into();
                    events.push(format!("fail\t{}\tdependency-failed", u));
                    progress = true;
                }
                continue;
            }
            if u.ends_with(".mount") {
                if let Some(what) = unit_parser::get_scalar(&eu.parsed, "Mount", "What") {
                    if let Some((_dev, ready)) = device_alias_resolver::resolve_what(&what, yard, sem) {
                        if !ready {
                            let st = states.get_mut(&u).unwrap();
                            st.state = State::Failed;
                            st.reason = "device-absent".into();
                            events.push(format!("fail\t{}\tdevice-absent", u));
                            progress = true;
                            continue;
                        }
                    }
                }
                if let Some(where_p) = unit_parser::get_scalar(&eu.parsed, "Mount", "Where") {
                    let _ = crate::mount_unit_codec::validate_mount_unit(&u, &where_p, sem);
                }
            }
            if u.ends_with(".automount") {
                let mount_name = format!("{}.mount", u.trim_end_matches(".automount"));
                if automount_mode == "start_mount" {
                    if let Some(st) = states.get_mut(&mount_name) {
                        st.state = State::Started;
                        st.reason = "started".into();
                    }
                } else if triggers.contains(&u) {
                    if let Some(st) = states.get_mut(&mount_name) {
                        if st.state == State::Queued || st.state == State::Waiting {
                            st.state = State::Ready;
                        }
                    }
                }
            }
            let mut final_state = State::Started;
            let mut reason = "started".to_string();
            if u.ends_with(".service") {
                if let Some(outc) = yard.service_outcomes.get(&u) {
                    if outc == "failure" {
                        final_state = State::Failed;
                        reason = "dependency-failed".into();
                    }
                }
            }
            let st = states.get_mut(&u).unwrap();
            st.state = final_state;
            st.reason = reason.clone();
            events.push(format!(
                "{}\t{}\t{}",
                if reason == "started" { "start" } else { "fail" },
                u,
                reason
            ));
            progress = true;
        }
        if !progress { break; }
    }
    Ok(SimResult { states, events })
}
