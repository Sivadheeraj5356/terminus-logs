//! Ordering cycle resolution and canonical witnesses.
use std::collections::{BTreeMap, BTreeSet};

use crate::boot_semantics::Semantics;
use crate::dependency_graph::Edge;
use crate::reconcile_failure;
use crate::transaction_builder::Transaction;

pub fn resolve(mut tx: Transaction, sem: &Semantics) -> Result<Transaction, i32> {
    let mode = sem.decide_or("CYCLE_BREAK", &["mode"], "explicit_ok");
    loop {
        if let Some(cycle) = find_order_cycle(&tx) {
            // try remove synthetic edges on cycle
            let mut removed = None;
            for e in tx.edges.iter() {
                if cycle.contains(&e.from) && cycle.contains(&e.to) && e.kind == "after" || e.kind == "before" {
                    if e.provenance.starts_with("default:") {
                        removed = Some(e.clone());
                        break;
                    } else if mode == "explicit_ok" {
                        removed = Some(e.clone());
                        break;
                    }
                }
            }
            // fix operator precedence bug in condition above — rewrite carefully
            let mut candidate = None;
            for e in &tx.edges {
                let on = cycle.contains(&e.from) && cycle.contains(&e.to);
                if !on { continue; }
                if e.kind != "before" && e.kind != "after" { continue; }
                if e.provenance.starts_with("default:") {
                    candidate = Some(e.clone());
                    break;
                }
            }
            if candidate.is_none() && mode == "explicit_ok" {
                for e in &tx.edges {
                    let on = cycle.contains(&e.from) && cycle.contains(&e.to);
                    if on && (e.kind == "before" || e.kind == "after") {
                        candidate = Some(e.clone());
                        break;
                    }
                }
            }
            let Some(edge) = candidate else {
                // irreducible explicit cycle
                let mut wit: Vec<String> = cycle.into_iter().collect();
                wit.sort();
                crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_DEPENDENCY_TX, &format!("cycle {}", wit.join(",")));
                return Err(reconcile_failure::EXIT_DEPENDENCY_TX);
            };
            tx.edges.retain(|e| !(e.from == edge.from && e.to == edge.to && e.kind == edge.kind && e.provenance == edge.provenance));
            tx.removed_synthetic.push(edge);
            let _ = removed;
        } else {
            break;
        }
    }
    Ok(tx)
}

fn find_order_cycle(tx: &Transaction) -> Option<BTreeSet<String>> {
    let mut adj: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for e in &tx.edges {
        if e.kind == "after" {
            adj.entry(e.from.clone()).or_default().push(e.to.clone());
        } else if e.kind == "before" {
            adj.entry(e.to.clone()).or_default().push(e.from.clone());
        }
    }
    let nodes: Vec<_> = tx.jobs.keys().cloned().collect();
    let mut color: BTreeMap<String, u8> = BTreeMap::new();
    let mut stack = Vec::new();
    for n in nodes {
        if dfs(&n, &adj, &mut color, &mut stack) {
            let mut set = BTreeSet::new();
            if let Some(start) = stack.last().cloned() {
                for x in stack.iter().rev() {
                    set.insert(x.clone());
                    if x == &start && set.len() > 1 { break; }
                }
            }
            for x in &stack { set.insert(x.clone()); }
            return Some(set);
        }
    }
    None
}

fn dfs(u: &str, adj: &BTreeMap<String, Vec<String>>, color: &mut BTreeMap<String, u8>, stack: &mut Vec<String>) -> bool {
    color.insert(u.to_string(), 1);
    stack.push(u.to_string());
    if let Some(ns) = adj.get(u) {
        for v in ns {
            let c = color.get(v).copied().unwrap_or(0);
            if c == 1 { stack.push(v.clone()); return true; }
            if c == 0 && dfs(v, adj, color, stack) { return true; }
        }
    }
    stack.pop();
    color.insert(u.to_string(), 2);
    false
}
