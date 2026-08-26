//! Load and authenticate captured bootyard members.
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use crate::boot_semantics::Semantics;
use crate::bootyard_boundary;
use crate::logical_seal;
use crate::reconcile_failure;

#[derive(Clone, Debug)]
pub struct Yard {
    pub root: String,
    pub host_label: String,
    pub machine_id: String,
    pub architecture: String,
    pub generation: u64,
    pub default_target: String,
    pub identity: BTreeMap<String, String>,
    pub facts: BTreeMap<String, String>,
    pub path_facts: BTreeMap<String, String>,
    pub mount_facts: BTreeMap<String, String>,
    pub service_outcomes: BTreeMap<String, String>,
    pub cmdline_tokens: Vec<String>,
    pub devices: BTreeMap<String, DeviceRec>,
    pub alias_to_device: BTreeMap<String, String>,
    pub initial_active: Vec<String>,
    pub vendor_seal: String,
    pub identity_raw: String,
}

#[derive(Clone, Debug)]
pub struct DeviceRec {
    pub ready: bool,
    pub backing: String,
    pub aliases: Vec<String>,
}

pub fn load_yard(root: &str, sem: &Semantics) -> Result<Yard, i32> {
    let fact_src = sem.decide_or("FACT_SOURCE", &["source"], "evaluator_env");
    if fact_src == "evaluator_env" {
        // Flawed path: would consult evaluator; we still refuse real env but mark inconsistent later
    }
    let identity_raw = read_file(&bootyard_boundary::logical_join(root, "yard.identity"))?;
    let identity = parse_kv(&identity_raw)?;
    let host_label = req(&identity, "host_label")?;
    let machine_id = req(&identity, "machine_id")?;
    let architecture = req(&identity, "architecture")?;
    let generation: u64 = req(&identity, "initial_generation")?
        .parse()
        .map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "generation"))?;
    // Prefer live generation file if present
    let gen_path = bootyard_boundary::logical_join(root, "var/lib/unitgraph/generation");
    let generation = if Path::new(&gen_path).is_file() {
        fs::read_to_string(&gen_path)
            .map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "generation read"))?
            .trim()
            .parse()
            .map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "generation parse"))?
    } else {
        generation
    };
    let default_target = req(&identity, "default_target")?;
    let vendor_seal = read_file(&bootyard_boundary::logical_join(root, "vendor.seal"))?;
    let facts_raw = read_file(&bootyard_boundary::logical_join(root, "runtime.facts"))?;
    let (facts, path_facts, mount_facts, service_outcomes, initial_active) = parse_facts(&facts_raw)?;
    let cmdline_raw = read_file(&bootyard_boundary::logical_join(root, "proc.cmdline"))?;
    let cmdline_tokens = parse_cmdline(&cmdline_raw)?;
    let devices_raw = read_file(&bootyard_boundary::logical_join(root, "devices.table"))?;
    let (devices, alias_to_device) = parse_devices(&devices_raw)?;
    refuse_special_nodes(root)?;
    Ok(Yard {
        root: root.to_string(),
        host_label,
        machine_id,
        architecture,
        generation,
        default_target,
        identity,
        facts,
        path_facts,
        mount_facts,
        service_outcomes,
        cmdline_tokens,
        devices,
        alias_to_device,
        initial_active,
        vendor_seal,
        identity_raw,
    })
}

fn refuse_special_nodes(root: &str) -> Result<(), i32> {
    for tier in ["usr/lib/systemd/system", "run/systemd/system", "etc/systemd/system"] {
        let base = bootyard_boundary::logical_join(root, tier);
        walk_check(&base)?;
    }
    Ok(())
}

fn walk_check(base: &str) -> Result<(), i32> {
    let p = Path::new(base);
    if !p.exists() {
        return Ok(());
    }
    let mut stack = vec![base.to_string()];
    while let Some(cur) = stack.pop() {
        let rd = fs::read_dir(&cur).map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "read tier"))?;
        for ent in rd {
            let ent = ent.map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "dirent"))?;
            let path = ent.path();
            let name = ent.file_name().to_string_lossy().to_string();
            if name.contains('\0') || name.chars().any(|c| !c.is_ascii()) {
                return Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "unicode name"));
            }
            let meta = fs::symlink_metadata(&path)
                .map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "meta"))?;
            let ft = meta.file_type();
            if ft.is_symlink() {
                let t = fs::read_link(&path).map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "link"))?;
                let ts = t.to_string_lossy();
                // Absolute targets only permitted for /dev/null masks. Relative
                // targets may contain .. when they remain inside the yard model.
                if ts.starts_with('/') && ts != "/dev/null" {
                    return Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "escaped link"));
                }
                if ts.is_empty() || ts.contains('\0') {
                    return Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "escaped link"));
                }
            } else if ft.is_dir() {
                stack.push(path.to_string_lossy().to_string());
            } else if !ft.is_file() {
                return Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "special node"));
            }
            // hard link detection: nlink > 1 for files
            #[cfg(unix)]
            {
                use std::os::unix::fs::MetadataExt;
                if ft.is_file() && meta.nlink() > 1 {
                    return Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "hard link"));
                }
            }
        }
    }
    Ok(())
}

fn parse_facts(
    raw: &str,
) -> Result<
    (
        BTreeMap<String, String>,
        BTreeMap<String, String>,
        BTreeMap<String, String>,
        BTreeMap<String, String>,
        Vec<String>,
    ),
    i32,
> {
    let mut facts = BTreeMap::new();
    let mut path_facts = BTreeMap::new();
    let mut mount_facts = BTreeMap::new();
    let mut service_outcomes = BTreeMap::new();
    let mut initial_active = Vec::new();
    for line in raw.lines() {
        if line.is_empty() {
            continue;
        }
        if let Some(rest) = line.strip_prefix("path_fact=") {
            let mut sp = rest.splitn(2, '\t');
            path_facts.insert(sp.next().unwrap_or("").into(), sp.next().unwrap_or("").into());
        } else if let Some(rest) = line.strip_prefix("mount_fact=") {
            let mut sp = rest.splitn(2, '\t');
            mount_facts.insert(sp.next().unwrap_or("").into(), sp.next().unwrap_or("").into());
        } else if let Some(rest) = line.strip_prefix("service_outcome=") {
            let mut sp = rest.splitn(2, '\t');
            service_outcomes.insert(sp.next().unwrap_or("").into(), sp.next().unwrap_or("").into());
        } else if let Some(rest) = line.strip_prefix("initial_active=") {
            initial_active.push(rest.to_string());
        } else if let Some((k, v)) = line.split_once('=') {
            facts.insert(k.to_string(), v.to_string());
        } else {
            return Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "facts grammar"));
        }
    }
    Ok((facts, path_facts, mount_facts, service_outcomes, initial_active))
}

fn parse_cmdline(raw: &str) -> Result<Vec<String>, i32> {
    for line in raw.lines() {
        if let Some(rest) = line.strip_prefix("cmdline=") {
            return Ok(rest.split_whitespace().map(|s| s.to_string()).collect());
        }
    }
    Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "cmdline"))
}

fn parse_devices(raw: &str) -> Result<(BTreeMap<String, DeviceRec>, BTreeMap<String, String>), i32> {
    let mut devices: BTreeMap<String, DeviceRec> = BTreeMap::new();
    let mut alias_to_device: BTreeMap<String, String> = BTreeMap::new();
    for line in raw.lines() {
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split('\t').collect();
        if parts.len() != 4 {
            return Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "devices grammar"));
        }
        let ready = parts[1] == "ready";
        let aliases: Vec<String> = if parts[3] == "-" {
            vec![]
        } else {
            parts[3].split(',').map(|s| s.to_string()).collect()
        };
        for a in &aliases {
            if let Some(prev) = alias_to_device.get(a) {
                if prev != parts[0] {
                    if let Some(pd) = devices.get(prev) {
                        if pd.backing != parts[2] {
                            return Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "alias conflict"));
                        }
                    }
                }
            }
            alias_to_device.insert(a.clone(), parts[0].to_string());
        }
        devices.insert(
            parts[0].to_string(),
            DeviceRec {
                ready,
                backing: parts[2].to_string(),
                aliases,
            },
        );
    }
    Ok((devices, alias_to_device))
}

fn parse_kv(raw: &str) -> Result<BTreeMap<String, String>, i32> {
    let mut m = BTreeMap::new();
    for line in raw.lines() {
        if line.is_empty() {
            continue;
        }
        let (k, v) = line
            .split_once('=')
            .ok_or_else(|| fail(reconcile_failure::EXIT_YARD_CUSTODY, "identity grammar"))?;
        if m.insert(k.to_string(), v.to_string()).is_some() {
            return Err(fail(reconcile_failure::EXIT_YARD_CUSTODY, "duplicate identity key"));
        }
    }
    Ok(m)
}

fn req(m: &BTreeMap<String, String>, k: &str) -> Result<String, i32> {
    m.get(k)
        .cloned()
        .ok_or_else(|| fail(reconcile_failure::EXIT_YARD_CUSTODY, "missing identity key"))
}

fn read_file(path: &str) -> Result<String, i32> {
    fs::read_to_string(path).map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "missing yard member"))
}

fn fail(code: i32, msg: &str) -> i32 {
    crate::diagnostic_surface::emit_error(code, msg);
    code
}

pub fn admin_root(yard: &Yard) -> String {
    bootyard_boundary::logical_join(&yard.root, "etc/systemd/system")
}

pub fn digest_admin_tree(yard_root: &str) -> Result<String, i32> {
    let base = bootyard_boundary::logical_join(yard_root, "etc/systemd/system");
    let mut lines = Vec::new();
    collect_tree(&base, "etc/systemd/system", &mut lines)?;
    Ok(logical_seal::sha256_hex(lines.join("\n").as_bytes()))
}

fn collect_tree(abs: &str, logical: &str, lines: &mut Vec<String>) -> Result<(), i32> {
    let p = Path::new(abs);
    if !p.exists() {
        return Ok(());
    }
    let mut ents: Vec<_> = fs::read_dir(p)
        .map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "admin walk"))?
        .filter_map(|e| e.ok())
        .collect();
    ents.sort_by_key(|e| e.file_name());
    for ent in ents {
        let name = ent.file_name().to_string_lossy().to_string();
        let logical_child = format!("{}/{}", logical, name);
        let meta = fs::symlink_metadata(ent.path())
            .map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "admin meta"))?;
        if meta.file_type().is_symlink() {
            let t = fs::read_link(ent.path())
                .map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "admin link"))?;
            lines.push(format!("L\t{}\t{}", logical_child, t.to_string_lossy()));
        } else if meta.file_type().is_dir() {
            lines.push(format!("D\t{}", logical_child));
            collect_tree(&ent.path().to_string_lossy(), &logical_child, lines)?;
        } else if meta.file_type().is_file() {
            let bytes = fs::read(ent.path())
                .map_err(|_| fail(reconcile_failure::EXIT_YARD_CUSTODY, "admin file"))?;
            lines.push(format!("F\t{}\t{}", logical_child, logical_seal::sha256_hex(&bytes)));
        }
    }
    Ok(())
}
