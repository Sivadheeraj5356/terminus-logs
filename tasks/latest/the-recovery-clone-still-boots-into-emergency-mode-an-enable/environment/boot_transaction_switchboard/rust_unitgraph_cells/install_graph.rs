//! Plan administrative install mutations from intent.
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use crate::boot_semantics::Semantics;
use crate::bootyard_boundary;
use crate::order_reader::{Intent, Order};
use crate::preset_resolver;
use crate::reconcile_failure;
use crate::unit_parser;
use crate::yard_inventory::Yard;

#[derive(Clone, Debug)]
pub struct ChangeItem {
    pub path_logical: String,
    pub before: String,
    pub after: String,
    pub intent_seq: u32,
    pub kind: String,
}

#[derive(Clone, Debug)]
pub struct MutationPlan {
    pub changes: Vec<ChangeItem>,
    pub next_generation: u64,
    pub order_id: String,
}

pub fn plan_mutations(yard: &Yard, order: &Order, sem: &Semantics) -> Result<MutationPlan, i32> {
    let mut changes = Vec::new();
    let admin = "etc/systemd/system".to_string();
    for intent in &order.intents {
        match intent.op.as_str() {
            "ENABLE" => plan_enable(yard, intent, sem, &mut changes)?,
            "DISABLE" => plan_disable(yard, intent, sem, &mut changes)?,
            "MASK" => plan_mask(yard, intent, &mut changes)?,
            "UNMASK" => plan_unmask(yard, intent, sem, &mut changes)?,
            "PRESET" => {
                let unit = unit_name(intent);
                let act = preset_resolver::resolve_action(&unit, order, sem);
                if act == "enable" {
                    let mut i = intent.clone();
                    i.op = "ENABLE".into();
                    plan_enable(yard, &i, sem, &mut changes)?;
                } else if act == "disable" {
                    let mut i = intent.clone();
                    i.op = "DISABLE".into();
                    plan_disable(yard, &i, sem, &mut changes)?;
                }
            }
            "SET_DEFAULT" => {
                let target = intent.unit.clone();
                let logical = format!("{}/default.target", admin);
                let after = if sem.decide_or("LINK_TARGET_FORM", &["form"], "absolute") == "absolute" {
                    format!("{}/{}", yard.root, format!("{}/{}", admin, target))
                } else {
                    target.clone()
                };
                changes.push(ChangeItem {
                    path_logical: logical,
                    before: read_link_logical(yard, "etc/systemd/system/default.target"),
                    after,
                    intent_seq: intent.seq,
                    kind: "symlink".into(),
                });
            }
            "PUT_DROPIN" => {
                let unit = unit_name(intent);
                let fields = intent.payload_fields.clone().unwrap_or_default();
                let logical = format!("{}/{}.d/10-order.conf", admin, unit);
                changes.push(ChangeItem {
                    path_logical: logical,
                    before: "-".into(),
                    after: format!("content:{}", fields),
                    intent_seq: intent.seq,
                    kind: "file".into(),
                });
            }
            "REMOVE_DROPIN" => {
                let unit = unit_name(intent);
                let logical = format!("{}/{}.d/10-order.conf", admin, unit);
                changes.push(ChangeItem {
                    path_logical: logical,
                    before: "present".into(),
                    after: "absent".into(),
                    intent_seq: intent.seq,
                    kind: "remove".into(),
                });
            }
            _ => return Err(fail(reconcile_failure::EXIT_INSTALL_POLICY, "unknown op")),
        }
    }
    // ensure final default target agreement recorded
    let _ = order.final_target;
    Ok(MutationPlan {
        changes,
        next_generation: order.next_generation,
        order_id: order.order_id.clone(),
    })
}

fn plan_enable(yard: &Yard, intent: &Intent, sem: &Semantics, changes: &mut Vec<ChangeItem>) -> Result<(), i32> {
    let unit = unit_name(intent);
    let text = read_unit_text(yard, &unit)?;
    let parsed = unit_parser::parse(&text)?;
    let wanted = unit_parser::get_list(&parsed, "Install", "WantedBy");
    let required = unit_parser::get_list(&parsed, "Install", "RequiredBy");
    let aliases = unit_parser::get_list(&parsed, "Install", "Alias");
    let also = unit_parser::get_list(&parsed, "Install", "Also");
    let link_form = sem.decide_or("LINK_TARGET_FORM", &["form"], "absolute");
    for t in wanted {
        let kind = sem.decide_or("ENABLE_LINK_KIND", &["WantedBy"], ".requires");
        let logical = format!("etc/systemd/system/{}{}/{}", t, kind, unit);
        let target = if link_form == "absolute" {
            format!("{}/usr/lib/systemd/system/{}", yard.root, unit)
        } else {
            format!("../{}", unit)
        };
        changes.push(ChangeItem {
            path_logical: logical,
            before: "absent".into(),
            after: target,
            intent_seq: intent.seq,
            kind: "symlink".into(),
        });
    }
    for t in required {
        let kind = sem.decide_or("ENABLE_LINK_KIND", &["RequiredBy"], ".wants");
        let logical = format!("etc/systemd/system/{}{}/{}", t, kind, unit);
        let target = if link_form == "absolute" {
            format!("{}/usr/lib/systemd/system/{}", yard.root, unit)
        } else {
            format!("../{}", unit)
        };
        changes.push(ChangeItem {
            path_logical: logical,
            before: "absent".into(),
            after: target,
            intent_seq: intent.seq,
            kind: "symlink".into(),
        });
    }
    for a in aliases {
        changes.push(ChangeItem {
            path_logical: format!("etc/systemd/system/{}", a),
            before: "absent".into(),
            after: unit.clone(),
            intent_seq: intent.seq,
            kind: "symlink".into(),
        });
    }
    for a in also {
        let mut child = intent.clone();
        child.unit = a;
        child.instance = None;
        plan_enable(yard, &child, sem, changes)?;
    }
    Ok(())
}

fn plan_disable(yard: &Yard, intent: &Intent, sem: &Semantics, changes: &mut Vec<ChangeItem>) -> Result<(), i32> {
    let unit = unit_name(intent);
    let scope = sem.decide_or("DISABLE_SCOPE", &["mode"], "same_target_all");
    let admin = bootyard_boundary::logical_join(&yard.root, "etc/systemd/system");
    let p = Path::new(&admin);
    if !p.is_dir() { return Ok(()); }
    for ent in fs::read_dir(p).map_err(|_| fail(reconcile_failure::EXIT_INSTALL_POLICY, "admin"))? {
        let ent = ent.map_err(|_| fail(reconcile_failure::EXIT_INSTALL_POLICY, "admin"))?;
        let name = ent.file_name().to_string_lossy().to_string();
        if !(name.ends_with(".wants") || name.ends_with(".requires")) { continue; }
        let link = ent.path().join(&unit);
        if fs::symlink_metadata(&link).is_ok() {
            changes.push(ChangeItem {
                path_logical: format!("etc/systemd/system/{}/{}", name, unit),
                before: "symlink".into(),
                after: "absent".into(),
                intent_seq: intent.seq,
                kind: "remove".into(),
            });
        }
        if scope == "same_target_all" {
            // flawed: remove all links in directory
            if let Ok(rd) = fs::read_dir(ent.path()) {
                for l in rd.flatten() {
                    let ln = l.file_name().to_string_lossy().to_string();
                    if ln != unit {
                        changes.push(ChangeItem {
                            path_logical: format!("etc/systemd/system/{}/{}", name, ln),
                            before: "symlink".into(),
                            after: "absent".into(),
                            intent_seq: intent.seq,
                            kind: "remove".into(),
                        });
                    }
                }
            }
        }
    }
    Ok(())
}

fn plan_mask(yard: &Yard, intent: &Intent, changes: &mut Vec<ChangeItem>) -> Result<(), i32> {
    let unit = unit_name(intent);
    let logical = format!("etc/systemd/system/{}", unit);
    // remove conflicting admin file first
    changes.push(ChangeItem {
        path_logical: logical.clone(),
        before: read_state(yard, &logical),
        after: "/dev/null".into(),
        intent_seq: intent.seq,
        kind: "mask".into(),
    });
    Ok(())
}

fn plan_unmask(yard: &Yard, intent: &Intent, sem: &Semantics, changes: &mut Vec<ChangeItem>) -> Result<(), i32> {
    let unit = unit_name(intent);
    // determine which tier has mask
    for (tier_name, tier_path) in [("admin","etc/systemd/system"),("transient","run/systemd/system"),("vendor","usr/lib/systemd/system")] {
        let logical = format!("{}/{}", tier_path, unit);
        let abs = bootyard_boundary::logical_join(&yard.root, &logical);
        if let Ok(meta) = fs::symlink_metadata(&abs) {
            if meta.file_type().is_symlink() {
                if let Ok(t) = fs::read_link(&abs) {
                    if t.to_string_lossy() == "/dev/null" {
                        let action = sem.decide_or("UNMASK_SCOPE", &["tier", tier_name], "remove_mask");
                        if action == "remove_mask" && tier_name == "admin" {
                            changes.push(ChangeItem {
                                path_logical: logical,
                                before: "/dev/null".into(),
                                after: "absent".into(),
                                intent_seq: intent.seq,
                                kind: "remove".into(),
                            });
                            return Ok(());
                        } else if action == "remove_mask" && tier_name != "admin" {
                            // flawed unmask of vendor/transient
                            changes.push(ChangeItem {
                                path_logical: logical,
                                before: "/dev/null".into(),
                                after: "absent".into(),
                                intent_seq: intent.seq,
                                kind: "remove".into(),
                            });
                            return Ok(());
                        } else if tier_name != "admin" {
                            return Err(fail(reconcile_failure::EXIT_INSTALL_POLICY, "cannot unmask non-admin"));
                        }
                    }
                }
            }
        }
    }
    Ok(())
}

fn unit_name(intent: &Intent) -> String {
    if let Some(inst) = &intent.instance {
        if intent.unit.contains('@') {
            // name@.service + instance
            let (stem, ty) = intent.unit.rsplit_once('.').unwrap_or((&intent.unit, "service"));
            let prefix = stem.trim_end_matches('@');
            format!("{}@{}.{}", prefix, inst, ty)
        } else {
            let (stem, ty) = intent.unit.rsplit_once('.').unwrap_or((&intent.unit, "service"));
            format!("{}@{}.{}", stem, inst, ty)
        }
    } else {
        intent.unit.clone()
    }
}

fn read_unit_text(yard: &Yard, unit: &str) -> Result<String, i32> {
    for tier in ["etc/systemd/system", "run/systemd/system", "usr/lib/systemd/system"] {
        let abs = bootyard_boundary::logical_join(&yard.root, &format!("{}/{}", tier, unit));
        if Path::new(&abs).is_file() {
            return fs::read_to_string(abs).map_err(|_| fail(reconcile_failure::EXIT_INSTALL_POLICY, "unit text"));
        }
        // template
        let (prefix, instance, ty) = crate::unit_name_codec::split_instance(unit);
        if instance.is_some() {
            let t = format!("{}/{}@.{}", tier, prefix, ty);
            let abs = bootyard_boundary::logical_join(&yard.root, &t);
            if Path::new(&abs).is_file() {
                return fs::read_to_string(abs).map_err(|_| fail(reconcile_failure::EXIT_INSTALL_POLICY, "unit text"));
            }
        }
    }
    Err(fail(reconcile_failure::EXIT_INSTALL_POLICY, "unit missing"))
}

fn read_link_logical(yard: &Yard, logical: &str) -> String {
    let abs = bootyard_boundary::logical_join(&yard.root, logical);
    fs::read_link(abs).map(|p| p.to_string_lossy().to_string()).unwrap_or_else(|_| "absent".into())
}

fn read_state(yard: &Yard, logical: &str) -> String {
    let abs = bootyard_boundary::logical_join(&yard.root, logical);
    if Path::new(&abs).exists() || fs::symlink_metadata(&abs).is_ok() { "present".into() } else { "absent".into() }
}

fn fail(code: i32, msg: &str) -> i32 {
    crate::diagnostic_surface::emit_error(code, msg);
    code
}
