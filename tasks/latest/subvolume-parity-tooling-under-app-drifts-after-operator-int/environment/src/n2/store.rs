use std::fs;
use std::path::Path;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JournalTail {
    pub journal_seq: u32,
    pub receiver_tail: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Checkpoint {
    pub lanes_witnessed: u32,
    pub last_lane_id: String,
}

pub fn journal_path(root: &Path) -> std::path::PathBuf {
    root.join("var/journal_tail.json")
}

pub fn checkpoint_path(root: &Path) -> std::path::PathBuf {
    root.join("var/checkpoint.json")
}

pub fn wrap_gen_path(root: &Path) -> std::path::PathBuf {
    root.join("var/wrap.gen")
}

pub fn ensure_var_layout(root: &Path) -> Result<(), String> {
    fs::create_dir_all(root.join("var/lane_cache")).map_err(|e| e.to_string())?;
    fs::create_dir_all(root.join("output")).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn read_journal(root: &Path) -> Result<JournalTail, String> {
    let path = journal_path(root);
    if !path.is_file() {
        return Ok(JournalTail {
            journal_seq: 1,
            receiver_tail: String::new(),
        });
    }
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

pub fn write_journal(root: &Path, tail: &JournalTail) -> Result<(), String> {
    let path = journal_path(root);
    let text = serde_json::to_string_pretty(tail).map_err(|e| e.to_string())?;
    fs::write(path, format!("{text}\n")).map_err(|e| e.to_string())
}

pub fn read_checkpoint(root: &Path) -> Result<Checkpoint, String> {
    let path = checkpoint_path(root);
    if !path.is_file() {
        return Ok(Checkpoint {
            lanes_witnessed: 0,
            last_lane_id: String::new(),
        });
    }
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

pub fn write_checkpoint(root: &Path, ckpt: &Checkpoint) -> Result<(), String> {
    let path = checkpoint_path(root);
    let text = serde_json::to_string_pretty(ckpt).map_err(|e| e.to_string())?;
    fs::write(path, format!("{text}\n")).map_err(|e| e.to_string())
}

pub fn read_wrap_gen(root: &Path) -> Result<u32, String> {
    let path = wrap_gen_path(root);
    if !path.is_file() {
        return Ok(1);
    }
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    text.trim()
        .parse::<u32>()
        .map_err(|e| format!("parse wrap.gen: {e}"))
}

pub fn write_wrap_gen(root: &Path, value: u32) -> Result<(), String> {
    let path = wrap_gen_path(root);
    fs::write(path, format!("{value}\n")).map_err(|e| e.to_string())
}
