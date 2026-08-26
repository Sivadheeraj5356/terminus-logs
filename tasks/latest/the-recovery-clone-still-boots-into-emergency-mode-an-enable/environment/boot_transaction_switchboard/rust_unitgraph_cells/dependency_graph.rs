//! Requirement and ordering edges with provenance.
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use crate::boot_semantics::Semantics;
use crate::bootyard_boundary;
use crate::fragment_locator::EffectiveUnit;
use crate::order_reader::Order;
use crate::unit_parser;

#[derive(Clone, Debug)]
pub struct Edge {
    pub from: String,
    pub to: String,
    pub kind: String,
    pub provenance: String,
}

#[derive(Clone, Debug, Default)]
pub struct DepGraph {
    pub edges: Vec<Edge>,
}

pub fn build(
    yard_root: &str,
    effective: &BTreeMap<String, EffectiveUnit>,
    order: &Order,
    sem: &Semantics,
) -> Result<DepGraph, i32> {
    let mut g = DepGraph::default();
    add_install_dir_edges(&mut g, yard_root, &order.final_target, "wants");
    add_install_dir_edges(&mut g, yard_root, &order.final_target, "requires");

    for (unit, eu) in effective {
        if eu.masked {
            continue;
        }
        for key in [
            "Wants",
            "Requires",
            "Requisite",
            "BindsTo",
            "PartOf",
            "Conflicts",
            "Before",
            "After",
        ] {
            for peer in unit_parser::get_list(&eu.parsed, "Unit", key) {
                let kind = match key {
                    "Requisite" | "BindsTo" | "PartOf" => {
                        let _def = key.to_lowercase();
                        sem.decide_or("EDGE_DISTINCT", &[key], "requires")
                    }
                    other => other.to_lowercase(),
                };
                g.edges.push(Edge {
                    from: unit.clone(),
                    to: peer,
                    kind,
                    provenance: format!("explicit:{}", key),
                });
            }
        }
        let dd = unit_parser::get_scalar(&eu.parsed, "Unit", "DefaultDependencies")
            .unwrap_or_else(|| "yes".into());
        let syn = sem.decide_or(
            "DEFAULT_DEPS",
            &[
                "DefaultDependencies",
                if dd == "no" { "no" } else { "yes" },
            ],
            if dd == "no" { "synthesize" } else { "omit" },
        );
        if syn == "synthesize" {
            let ty = unit.rsplit('.').next().unwrap_or("");
            match ty {
                "service" => {
                    g.edges.push(Edge {
                        from: unit.clone(),
                        to: "basic.target".into(),
                        kind: "after".into(),
                        provenance: "default:service-basic".into(),
                    });
                }
                "target" if unit != "basic.target" => {
                    g.edges.push(Edge {
                        from: unit.clone(),
                        to: "basic.target".into(),
                        kind: "after".into(),
                        provenance: "default:target-basic".into(),
                    });
                }
                "mount" => {
                    g.edges.push(Edge {
                        from: unit.clone(),
                        to: "local-fs.target".into(),
                        kind: "before".into(),
                        provenance: "default:mount-fs".into(),
                    });
                    if sem.decide_or("PARENT_MOUNT", &["mode"], "omit") == "synthesize" {
                        if let Some(where_p) = unit_parser::get_scalar(&eu.parsed, "Mount", "Where")
                        {
                            if let Some(parent) = parent_mount_unit(&where_p) {
                                if effective.contains_key(&parent) {
                                    g.edges.push(Edge {
                                        from: unit.clone(),
                                        to: parent,
                                        kind: "requires".into(),
                                        provenance: "default:parent-mount".into(),
                                    });
                                }
                            }
                        }
                    }
                }
                "automount" => {
                    g.edges.push(Edge {
                        from: unit.clone(),
                        to: "local-fs.target".into(),
                        kind: "before".into(),
                        provenance: "default:automount".into(),
                    });
                }
                "path" => {
                    g.edges.push(Edge {
                        from: unit.clone(),
                        to: "paths.target".into(),
                        kind: "before".into(),
                        provenance: "default:path".into(),
                    });
                }
                _ => {}
            }
        }
    }
    let _ = BTreeSet::<String>::new();
    Ok(g)
}

fn add_install_dir_edges(g: &mut DepGraph, yard: &str, target: &str, kind: &str) {
    for tier in [
        "etc/systemd/system",
        "run/systemd/system",
        "usr/lib/systemd/system",
    ] {
        let dir = bootyard_boundary::logical_join(yard, &format!("{}/{}.{}", tier, target, kind));
        let p = Path::new(&dir);
        if !p.is_dir() {
            continue;
        }
        let Ok(rd) = fs::read_dir(p) else {
            continue;
        };
        for ent in rd.flatten() {
            let name = ent.file_name().to_string_lossy().to_string();
            g.edges.push(Edge {
                from: target.to_string(),
                to: name,
                kind: if kind == "requires" {
                    "requires".into()
                } else {
                    "wants".into()
                },
                provenance: format!("install:{}.{}", target, kind),
            });
        }
    }
}

fn parent_mount_unit(where_p: &str) -> Option<String> {
    if where_p == "/" {
        return None;
    }
    let p = where_p.trim_end_matches('/');
    let parent = path_parent(p)?;
    if parent == "/" {
        return Some("-.mount".into());
    }
    let stem = crate::unit_name_codec::escape_path(parent).ok()?;
    Some(format!("{}.mount", stem))
}

fn path_parent(p: &str) -> Option<&str> {
    let p = p.trim_end_matches('/');
    let idx = p.rfind('/')?;
    if idx == 0 {
        Some("/")
    } else {
        Some(&p[..idx])
    }
}
