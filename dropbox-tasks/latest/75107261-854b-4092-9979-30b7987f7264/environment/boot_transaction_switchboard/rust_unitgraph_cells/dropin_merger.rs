//! Drop-in family/tier/basename merge.
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use crate::boot_semantics::Semantics;
use crate::bootyard_boundary;
use crate::reconcile_failure;
use crate::unit_parser::{self, ParsedUnit};

pub fn merge_dropins(
    yard_root: &str,
    unit: &str,
    base: &ParsedUnit,
    sem: &Semantics,
) -> Result<(ParsedUnit, Vec<String>), i32> {
    let mode = sem.decide_or("DROPIN_ORDER", &["mode"], "global_basename");
    let families = dropin_families(unit);
    let tiers = tier_order(sem);
    let mut by_basename: BTreeMap<String, (usize, String, String)> = BTreeMap::new();
    // value: (tier_rank, family_rank encoded in path, abs path)
    for (fi, fam) in families.iter().enumerate() {
        for (ti, tier) in tiers.iter().enumerate() {
            let dir = bootyard_boundary::logical_join(yard_root, &format!("{}/{}", tier, fam));
            let p = Path::new(&dir);
            if !p.is_dir() { continue; }
            let mut ents: Vec<_> = fs::read_dir(p).map_err(|_| e())?.filter_map(|x| x.ok()).collect();
            ents.sort_by_key(|x| x.file_name());
            for ent in ents {
                let name = ent.file_name().to_string_lossy().to_string();
                if !name.ends_with(".conf") { continue; }
                let abs = ent.path().to_string_lossy().to_string();
                if mode == "global_basename" {
                    // flawed: ignore family/tier, last alphabetically wins globally later
                    by_basename.insert(name.clone(), (1000 - ti, format!("{:04}", fi), abs));
                } else {
                    // highest tier wins for basename; family applied in order later
                    let key = format!("{:04}:{}", fi, name);
                    by_basename.entry(key).or_insert((ti, name.clone(), abs));
                }
            }
        }
    }
    let mut contrib = Vec::new();
    let mut merged = base.clone();
    let mut items: Vec<_> = by_basename.into_iter().collect();
    if mode == "global_basename" {
        items.sort_by(|a, b| a.0.cmp(&b.0));
    } else {
        items.sort_by(|a, b| a.0.cmp(&b.0));
    }
    for (_k, (_tr, _nm, abs)) in items {
        let text = fs::read_to_string(&abs).map_err(|_| e())?;
        let part = unit_parser::parse(&text)?;
        apply_merge(&mut merged, &part, sem)?;
        contrib.push(abs);
    }
    Ok((merged, contrib))
}

fn apply_merge(dst: &mut ParsedUnit, src: &ParsedUnit, sem: &Semantics) -> Result<(), i32> {
    let list_reset = sem.decide_or("EMPTY_LIST_RESET", &["list_empty_assign"], "keep");
    let scalar_empty = sem.decide_or("SCALAR_EMPTY", &["scalar_empty_assign"], "reset");
    for (sec, keys) in &src.sections {
        let dsec = dst.sections.entry(sec.clone()).or_default();
        for (k, vals) in keys {
            let is_list = matches!(k.as_str(),
                "Requires"|"Wants"|"Requisite"|"BindsTo"|"PartOf"|"Conflicts"|"Before"|"After"|
                "WantedBy"|"RequiredBy"|"Alias"|"Also"|"ConditionPathExists"|"AssertPathExists");
            if vals.len() == 1 && vals[0].is_empty() {
                if is_list {
                    if list_reset == "reset" { dsec.insert(k.clone(), vec![]); }
                } else if scalar_empty == "reset" {
                    dsec.remove(k);
                }
                continue;
            }
            if is_list {
                dsec.entry(k.clone()).or_default().extend(vals.iter().cloned().filter(|v| !v.is_empty()));
            } else if let Some(last) = vals.last() {
                dsec.insert(k.clone(), vec![last.clone()]);
            }
        }
    }
    Ok(())
}

fn dropin_families(unit: &str) -> Vec<String> {
    let mut out = Vec::new();
    let (stem, ty) = unit.rsplit_once('.').unwrap_or((unit, ""));
    out.push(format!("{}.d", ty)); // type family broadest
    // dash prefixes
    if let Some((pre, _inst)) = stem.split_once('@') {
        let parts: Vec<&str> = pre.split('-').collect();
        let mut acc = String::new();
        for (i, p) in parts.iter().enumerate() {
            if i > 0 { acc.push('-'); }
            acc.push_str(p);
            if i + 1 < parts.len() {
                out.push(format!("{}-.{}d", acc, format!("{}.", ty).trim_end_matches('.').to_string() + "."));
            }
        }
        // fix dash-prefix properly
    }
    // redo dash-prefix cleanly
    out.clear();
    out.push(format!("{}.d", ty));
    let name_for_prefix = if let Some((p, _)) = stem.split_once('@') { p } else { stem };
    let parts: Vec<&str> = name_for_prefix.split('-').collect();
    if parts.len() > 1 {
        let mut acc = String::new();
        for i in 0..parts.len()-1 {
            if i > 0 { acc.push('-'); }
            acc.push_str(parts[i]);
            out.push(format!("{}-.{}.d", acc, ty));
        }
    }
    if stem.contains('@') {
        let (p, _) = stem.split_once('@').unwrap();
        out.push(format!("{}@.{}.d", p, ty));
    }
    out.push(format!("{}.d", unit));
    out
}

fn tier_order(sem: &Semantics) -> Vec<String> {
    let order = sem.decide_or("FRAGMENT_TIER_ORDER", &["lookup"], "transient,admin,vendor");
    order.split(',').map(|s| match s.trim() {
        "admin" => "etc/systemd/system".into(),
        "transient" => "run/systemd/system".into(),
        "vendor" => "usr/lib/systemd/system".into(),
        other => other.to_string(),
    }).collect()
}

fn e() -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_UNIT_LOADING, "dropin");
    reconcile_failure::EXIT_UNIT_LOADING
}
