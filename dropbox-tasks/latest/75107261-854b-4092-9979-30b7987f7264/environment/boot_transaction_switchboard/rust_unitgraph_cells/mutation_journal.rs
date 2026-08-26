//! Shadow staging, publish exchange, rollback, change account.
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use crate::boot_semantics::Semantics;
use crate::bootyard_boundary;
use crate::install_graph::MutationPlan;
use crate::reconcile_failure;

pub fn stage_shadow(yard: &str, plan: &MutationPlan, sem: &Semantics) -> Result<String, i32> {
    let timing = sem.decide_or("GENERATION_TIMING", &["advance"], "before_verify");
    let shadow = format!("{}.unitgraph_shadow", yard);
    if Path::new(&shadow).exists() {
        fs::remove_dir_all(&shadow).map_err(|_| err("shadow clean"))?;
    }
    copy_dir(yard, &shadow)?;
    // optionally wrongly advance generation early
    if timing == "before_verify" {
        let gpath = bootyard_boundary::logical_join(&shadow, "var/lib/unitgraph/generation");
        fs::create_dir_all(Path::new(&gpath).parent().unwrap()).map_err(|_| err("gen dir"))?;
        fs::write(&gpath, format!("{}\n", plan.next_generation)).map_err(|_| err("gen write"))?;
    }
    // fault injection env for tests
    if let Ok(v) = std::env::var("UNITGRAPH_INJECT_WRITE_FAULT") {
        if v == "1" {
            restore_from_snapshot(yard, &shadow)?;
            fs::remove_dir_all(&shadow).ok();
            return Err(err("injected write fault"));
        }
    }
    Ok(shadow)
}

pub fn publish_exchange(yard: &str, staged: &str, plan: &MutationPlan) -> Result<(), i32> {
    // exchange etc/systemd/system and var/lib/unitgraph
    let pairs = [
        ("etc/systemd/system", "etc/systemd/system"),
        ("var/lib/unitgraph", "var/lib/unitgraph"),
    ];
    for (rel, _) in pairs {
        let dst = bootyard_boundary::logical_join(yard, rel);
        let src = bootyard_boundary::logical_join(staged, rel);
        let bak = format!("{}.bak_exchange", dst);
        if Path::new(&dst).exists() {
            if Path::new(&bak).exists() { fs::remove_dir_all(&bak).ok(); }
            fs::rename(&dst, &bak).map_err(|_| err("rename bak"))?;
        }
        // move src into place
        if let Some(parent) = Path::new(&dst).parent() {
            fs::create_dir_all(parent).map_err(|_| err("parent"))?;
        }
        fs::rename(&src, &dst).map_err(|_| {
            // rollback
            if Path::new(&bak).exists() {
                let _ = fs::rename(&bak, &dst);
            }
            err("rename publish")
        })?;
        if Path::new(&bak).exists() {
            fs::remove_dir_all(&bak).ok();
        }
    }
    // ensure generation written if not early
    let gpath = bootyard_boundary::logical_join(yard, "var/lib/unitgraph/generation");
    fs::write(&gpath, format!("{}\n", plan.next_generation)).map_err(|_| err("gen final"))?;
    Ok(())
}

pub fn cleanup_shadows(yard: &str) -> Result<(), i32> {
    let shadow = format!("{}.unitgraph_shadow", yard);
    if Path::new(&shadow).exists() {
        fs::remove_dir_all(&shadow).map_err(|_| err("cleanup"))?;
    }
    Ok(())
}

pub fn render_account(plan: &MutationPlan) -> Result<String, i32> {
    let mut lines = Vec::new();
    for ch in &plan.changes {
        lines.push(format!(
            "{}\t{}\t{}\t{}\t{}",
            ch.intent_seq, ch.path_logical, ch.kind, ch.before, ch.after
        ));
    }
    lines.sort();
    Ok(lines.join("\n") + "\n")
}

fn copy_dir(src: &str, dst: &str) -> Result<(), i32> {
    // use cp -a via recursive walk to preserve symlinks
    fs::create_dir_all(dst).map_err(|_| err("mkdir dst"))?;
    walk_copy(Path::new(src), Path::new(dst))?;
    Ok(())
}

fn walk_copy(src: &Path, dst: &Path) -> Result<(), i32> {
    for ent in fs::read_dir(src).map_err(|_| err("rd"))? {
        let ent = ent.map_err(|_| err("ent"))?;
        let sp = ent.path();
        let dp = dst.join(ent.file_name());
        let meta = fs::symlink_metadata(&sp).map_err(|_| err("meta"))?;
        if meta.file_type().is_dir() {
            fs::create_dir_all(&dp).map_err(|_| err("mkdir"))?;
            walk_copy(&sp, &dp)?;
        } else if meta.file_type().is_symlink() {
            let t = fs::read_link(&sp).map_err(|_| err("rl"))?;
            if dp.exists() || fs::symlink_metadata(&dp).is_ok() {
                fs::remove_file(&dp).ok();
            }
            std::os::unix::fs::symlink(t, &dp).map_err(|_| err("sl"))?;
        } else {
            fs::copy(&sp, &dp).map_err(|_| err("cp"))?;
        }
    }
    Ok(())
}

fn restore_from_snapshot(_yard: &str, _shadow: &str) -> Result<(), i32> {
    Ok(())
}

fn err(msg: &str) -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_MUTATION, msg);
    reconcile_failure::EXIT_MUTATION
}

pub fn snapshot_mutable(yard: &str) -> Result<PathBuf, i32> {
    let snap = format!("{}.unitgraph_presnap", yard);
    if Path::new(&snap).exists() { fs::remove_dir_all(&snap).ok(); }
    copy_dir(yard, &snap)?;
    Ok(PathBuf::from(snap))
}
