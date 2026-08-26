//! Narrow pure rule-capsule evaluator for defect-bearing decisions.
use std::collections::BTreeMap;
use std::os::fd::RawFd;

use crate::embedded_boot_semantics;
use crate::reconcile_failure::{self, Fail};

const SEMANTICS_FD: RawFd = 193;

#[derive(Clone, Debug)]
pub struct Semantics {
    tables: BTreeMap<String, BTreeMap<String, (String, String)>>,
}

impl Semantics {
    pub fn load() -> Result<Self, i32> {
        if let Some(bytes) = try_load_sealed_memfd() {
            return parse_bgr1(&bytes).map_err(|e| {
                crate::diagnostic_surface::emit_error(e.code, &e.msg);
                e.code
            });
        }
        parse_bgr1(embedded_boot_semantics::EMBEDDED_BGR1).map_err(|e| {
            crate::diagnostic_surface::emit_error(e.code, &e.msg);
            e.code
        })
    }

    pub fn decide(&self, rule: &str, keys: &[&str]) -> Result<(String, String), Fail> {
        let key = keys.join("|");
        let table = self
            .tables
            .get(rule)
            .ok_or_else(|| Fail::new(reconcile_failure::EXIT_UNIT_LOADING, "missing rule"))?;
        table
            .get(&key)
            .cloned()
            .ok_or_else(|| Fail::new(reconcile_failure::EXIT_UNIT_LOADING, "missing rule row"))
    }

    pub fn decide_or(&self, rule: &str, keys: &[&str], default: &str) -> String {
        self.decide(rule, keys)
            .map(|(v, _)| v)
            .unwrap_or_else(|_| default.to_string())
    }
}

fn try_load_sealed_memfd() -> Option<Vec<u8>> {
    #[cfg(target_os = "linux")]
    {
        use std::fs::File;
        use std::io::Read;
        use std::os::fd::FromRawFd;
        unsafe {
            let seals = libc_get_seals(SEMANTICS_FD);
            if seals < 0 {
                return None;
            }
            const F_SEAL_SEAL: i32 = 0x0001;
            const F_SEAL_SHRINK: i32 = 0x0002;
            const F_SEAL_GROW: i32 = 0x0004;
            const F_SEAL_WRITE: i32 = 0x0008;
            let need = F_SEAL_SEAL | F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_WRITE;
            if seals & need != need {
                return None;
            }
            // Rewind in case a prior reader left the offset at EOF.
            extern "C" {
                fn lseek(fd: i32, offset: i64, whence: i32) -> i64;
            }
            if lseek(SEMANTICS_FD, 0, 0) < 0 {
                return None;
            }
            let mut f = File::from_raw_fd(SEMANTICS_FD);
            let mut buf = Vec::new();
            if f.read_to_end(&mut buf).is_err() {
                std::mem::forget(f);
                return None;
            }
            // Rewind again so cold-replay children can reread the capsule.
            let _ = lseek(SEMANTICS_FD, 0, 0);
            std::mem::forget(f);
            if !buf.starts_with(b"BGR1\n") {
                return None;
            }
            Some(buf)
        }
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = SEMANTICS_FD;
        None
    }
}

#[cfg(target_os = "linux")]
unsafe fn libc_get_seals(fd: RawFd) -> i32 {
    const F_GET_SEALS: i32 = 1034;
    extern "C" {
        fn fcntl(fd: i32, cmd: i32, ...) -> i32;
    }
    fcntl(fd, F_GET_SEALS)
}

fn parse_bgr1(bytes: &[u8]) -> Result<Semantics, Fail> {
    let text = std::str::from_utf8(bytes)
        .map_err(|_| Fail::new(reconcile_failure::EXIT_UNIT_LOADING, "bgr1 utf8"))?;
    let mut lines = text.lines();
    if lines.next() != Some("BGR1") {
        return Err(Fail::new(reconcile_failure::EXIT_UNIT_LOADING, "bgr1 header"));
    }
    let mut digest = String::new();
    for line in lines.by_ref() {
        if line == "---" {
            break;
        }
        if let Some(v) = line.strip_prefix("digest=") {
            digest = v.to_string();
        }
    }
    let parts: Vec<&str> = text.splitn(2, "---\n").collect();
    if parts.len() != 2 {
        return Err(Fail::new(reconcile_failure::EXIT_UNIT_LOADING, "bgr1 payload"));
    }
    let payload = parts[1];
    let got = crate::logical_seal::sha256_hex(payload.as_bytes());
    if got != digest {
        return Err(Fail::new(reconcile_failure::EXIT_UNIT_LOADING, "bgr1 digest"));
    }
    let mut tables = BTreeMap::new();
    let mut cur: Option<String> = None;
    let mut in_table = false;
    for line in payload.lines() {
        if let Some(rest) = line.strip_prefix("RULE ") {
            cur = Some(rest.to_string());
            tables.insert(rest.to_string(), BTreeMap::new());
            in_table = false;
            continue;
        }
        if line == "TABLE" {
            in_table = true;
            continue;
        }
        if line == "END" {
            in_table = false;
            cur = None;
            continue;
        }
        if in_table {
            if let Some(rid) = cur.as_ref() {
                let mut sp = line.splitn(2, " -> ");
                let k = sp.next().unwrap_or("").to_string();
                let vpart = sp.next().unwrap_or("");
                let mut vr = vpart.splitn(2, '|');
                let v = vr.next().unwrap_or("").to_string();
                let r = vr.next().unwrap_or("").to_string();
                tables.get_mut(rid).unwrap().insert(k, (v, r));
            }
        }
    }
    Ok(Semantics { tables })
}
