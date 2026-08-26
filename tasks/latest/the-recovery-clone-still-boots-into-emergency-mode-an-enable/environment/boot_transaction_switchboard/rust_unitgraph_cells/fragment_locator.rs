//! Locate main fragments across tiers with mask/template rules.
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use crate::alias_mask_state;
use crate::boot_semantics::Semantics;
use crate::bootyard_boundary;
use crate::dropin_merger;
use crate::order_reader::Order;
use crate::reconcile_failure;
use crate::specifier_expander;
use crate::unit_name_codec;
use crate::unit_parser::{self, ParsedUnit};
use crate::yard_inventory::Yard;

#[derive(Clone, Debug)]
pub struct EffectiveUnit {
    pub name: String,
    pub fragment_logical: String,
    pub masked: bool,
    pub origin: String,
    pub parsed: ParsedUnit,
    pub dropins: Vec<String>,
    pub classification: String,
}

pub fn build_effective(
    yard_root: &str,
    order: &Order,
    sem: &Semantics,
) -> Result<BTreeMap<String, EffectiveUnit>, i32> {
    // Load yard facts wrapper minimally via reading runtime — caller passes staged root
    // We need Yard for specifiers; reconstruct lightly
    let yard = crate::yard_inventory::load_yard(yard_root, sem)?;
    let mut names = BTreeMap::new();
    names.insert(order.final_target.clone(), ());
    for intent in &order.intents {
        let u = if let Some(inst) = &intent.instance {
            let (stem, ty) = intent.unit.rsplit_once('.').unwrap_or((&intent.unit, "service"));
            if intent.unit.contains('@') {
                intent.unit.clone()
            } else {
                format!("{}@{}.{}", stem.trim_end_matches('@'), inst, ty)
            }
        } else {
            intent.unit.clone()
        };
        names.insert(u, ());
    }
    for a in &order.acceptance {
        names.insert(a.unit.clone(), ());
    }
    for m in &order.target_members {
        names.insert(m.clone(), ());
    }
    // also discover units from admin wants of final target
    discover_from_target(yard_root, &order.final_target, &mut names)?;

    let mut out = BTreeMap::new();
    for name in names.keys() {
        if let Some(eu) = load_one(yard_root, name, &yard, sem)? {
            out.insert(name.clone(), eu);
        }
    }
    Ok(out)
}

fn discover_from_target(yard: &str, target: &str, names: &mut BTreeMap<String, ()>) -> Result<(), i32> {
    names.insert(target.to_string(), ());
    for kind in [".wants", ".requires"] {
        let dir = bootyard_boundary::logical_join(yard, &format!("etc/systemd/system/{}{}", target, kind));
        let p = Path::new(&dir);
        if !p.is_dir() { continue; }
        for ent in fs::read_dir(p).map_err(|_| err())? {
            let ent = ent.map_err(|_| err())?;
            names.insert(ent.file_name().to_string_lossy().to_string(), ());
        }
    }
    Ok(())
}

fn load_one(yard: &str, name: &str, y: &Yard, sem: &Semantics) -> Result<Option<EffectiveUnit>, i32> {
    let mask_mode = sem.decide_or("MASK_OVERRIDE", &["low_tier_mask", "high_tier_file"], "file_wins");
    let (resolved, masked_alias) = alias_mask_state::resolve_alias_chain(yard, name, sem)?;
    let tiers = tier_paths(sem);
    // First pass: find masks across tiers respecting mask_mode
    let mut mask_tier: Option<usize> = None;
    let mut file_tier: Option<(usize, String, String)> = None; // tier, abs, logical
    for (ti, tier) in tiers.iter().enumerate() {
        let logical = format!("{}/{}", tier, resolved);
        let abs = bootyard_boundary::logical_join(yard, &logical);
        let path = Path::new(&abs);
        let meta = match fs::symlink_metadata(path) {
            Ok(m) => m,
            Err(_) => continue,
        };
        if meta.file_type().is_symlink() {
            let t = fs::read_link(path).map_err(|_| err())?;
            if t.to_string_lossy() == "/dev/null" {
                mask_tier = Some(ti);
                break; // highest-precedence tier in our order hits first
            }
        } else if meta.file_type().is_file() {
            file_tier = Some((ti, abs, logical));
            break;
        }
    }
    // Template fallback
    let mut used_template = false;
    let mut fragment = file_tier;
    if fragment.is_none() {
        let fb = sem.decide_or("TEMPLATE_FALLBACK", &["exact_missing"], "reject");
        let (prefix, instance, ty) = unit_name_codec::split_instance(&resolved);
        if instance.is_some() && fb == "use_template" {
            let tname = format!("{}@.{}", prefix, ty);
            for (ti, tier) in tiers.iter().enumerate() {
                let logical = format!("{}/{}", tier, tname);
                let abs = bootyard_boundary::logical_join(yard, &logical);
                if Path::new(&abs).is_file() {
                    fragment = Some((ti, abs, logical));
                    used_template = true;
                    break;
                }
            }
        } else if instance.is_some() && fb == "reject" {
            return Ok(None);
        }
    }
    let masked = masked_alias || mask_tier.is_some();
    if masked {
        if let (Some(mt), Some((ft, _, _))) = (mask_tier, fragment.clone()) {
            if mask_mode == "file_wins" && ft < mt {
                // flawed: higher-precedence file beats lower mask — ignore mask
            } else {
                return Ok(Some(EffectiveUnit {
                    name: name.to_string(),
                    fragment_logical: "mask:/dev/null".into(),
                    masked: true,
                    origin: "mask".into(),
                    parsed: ParsedUnit::default(),
                    dropins: vec![],
                    classification: "masked".into(),
                }));
            }
        } else if mask_tier.is_some() || masked_alias {
            return Ok(Some(EffectiveUnit {
                name: name.to_string(),
                fragment_logical: "mask:/dev/null".into(),
                masked: true,
                origin: "mask".into(),
                parsed: ParsedUnit::default(),
                dropins: vec![],
                classification: "masked".into(),
            }));
        }
    }
    let Some((_ti, abs, logical)) = fragment else {
        return Ok(None);
    };
    let text = fs::read_to_string(&abs).map_err(|_| err())?;
    let parsed = unit_parser::parse(&text)?;
    let (mut merged, dropins) = dropin_merger::merge_dropins(yard, name, &parsed, sem)?;
    if masked {
        // still masked
    }
    specifier_expander::expand_unit(&mut merged, name, y, sem);
    let origin = if used_template { "template" } else { "fragment" };
    let _ = y;
    Ok(Some(EffectiveUnit {
        name: name.to_string(),
        fragment_logical: logical,
        masked: false,
        origin: origin.into(),
        parsed: merged,
        dropins,
        classification: "loaded".into(),
    }))
}

fn tier_paths(sem: &Semantics) -> Vec<String> {
    let order = sem.decide_or("FRAGMENT_TIER_ORDER", &["lookup"], "transient,admin,vendor");
    order.split(',').map(|s| match s.trim() {
        "admin" => "etc/systemd/system".into(),
        "transient" => "run/systemd/system".into(),
        "vendor" => "usr/lib/systemd/system".into(),
        o => o.to_string(),
    }).collect()
}

fn err() -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_UNIT_LOADING, "fragment");
    reconcile_failure::EXIT_UNIT_LOADING
}
