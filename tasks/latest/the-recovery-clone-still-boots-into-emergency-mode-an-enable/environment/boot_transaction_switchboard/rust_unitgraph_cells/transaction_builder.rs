//! Pull jobs into the start transaction.
use std::collections::{BTreeMap, BTreeSet, VecDeque};

use crate::boot_semantics::Semantics;
use crate::dependency_graph::{DepGraph, Edge};
use crate::fragment_locator::EffectiveUnit;
use crate::order_reader::Order;
use crate::reconcile_failure;

#[derive(Clone, Debug)]
pub struct Job {
    pub unit: String,
    pub kind: String, // start|stop
    pub origins: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct Transaction {
    pub jobs: BTreeMap<String, Job>,
    pub edges: Vec<Edge>,
    pub removed_synthetic: Vec<Edge>,
}

pub fn build(
    dep: &DepGraph,
    effective: &BTreeMap<String, EffectiveUnit>,
    order: &Order,
    sem: &Semantics,
) -> Result<Transaction, i32> {
    let mut jobs: BTreeMap<String, Job> = BTreeMap::new();
    let mut q = VecDeque::new();
    q.push_back(order.final_target.clone());
    jobs.insert(order.final_target.clone(), Job { unit: order.final_target.clone(), kind: "start".into(), origins: vec!["seed".into()] });
    while let Some(u) = q.pop_front() {
        for e in dep.edges.iter().filter(|e| e.from == u) {
            let pulls = match e.kind.as_str() {
                "wants" | "requires" | "bindsto" => true,
                "before" | "after" => sem.decide_or("ORDERING_PULL", &[&capitalize(&e.kind)], "pull") == "pull",
                "requisite" | "partof" | "conflicts" => false,
                _ => false,
            };
            if e.kind == "conflicts" {
                jobs.entry(e.to.clone()).or_insert_with(|| Job { unit: e.to.clone(), kind: "stop".into(), origins: vec![e.provenance.clone()] });
                continue;
            }
            if pulls {
                if let Some(eu) = effective.get(&e.to) {
                    if eu.masked { continue; }
                }
                if !jobs.contains_key(&e.to) {
                    jobs.insert(e.to.clone(), Job { unit: e.to.clone(), kind: "start".into(), origins: vec![e.provenance.clone()] });
                    q.push_back(e.to.clone());
                } else {
                    jobs.get_mut(&e.to).unwrap().origins.push(e.provenance.clone());
                }
            }
        }
        // also pull from .wants/.requires directories — already in effective discovery
    }
    // keep only edges between jobs present (plus conflict stops)
    let names: BTreeSet<_> = jobs.keys().cloned().collect();
    let edges: Vec<_> = dep.edges.iter().filter(|e| names.contains(&e.from) && names.contains(&e.to)).cloned().collect();
    let _ = reconcile_failure::EXIT_DEPENDENCY_TX;
    Ok(Transaction { jobs, edges, removed_synthetic: vec![] })
}

fn capitalize(s: &str) -> String {
    let mut c = s.chars();
    match c.next() {
        None => String::new(),
        Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
    }
}
