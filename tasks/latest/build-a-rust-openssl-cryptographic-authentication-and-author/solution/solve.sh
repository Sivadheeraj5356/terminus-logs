#!/bin/bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}"

ROOT=/app/seal_authz
mkdir -p "$ROOT/src" /app/bin /app/output

cp /app/vault_scaffold/Cargo.toml "$ROOT/Cargo.toml"
cp /app/vault_scaffold/Cargo.lock "$ROOT/Cargo.lock"
mkdir -p "$ROOT/.cargo"
cp /app/vault_scaffold/.cargo/config.toml "$ROOT/.cargo/config.toml"

cat > "$ROOT/src/main.rs" <<'RS'
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process;

use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use openssl::hash::{hash, MessageDigest};
use openssl::pkey::PKey;
use openssl::sign::{Signer, Verifier};
use openssl::symm::{decrypt_aead, Cipher};
use rusqlite::{params, Connection};
use serde::Deserialize;
use serde_json::{json, Map, Value};

#[derive(Debug, Deserialize)]
struct Policy {
    authorized_classes: Vec<String>,
    decrypt_plaintext_for: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct Claim {
    report_id: String,
    category: String,
    label_ciphertext: String,
    label_nonce: String,
    label_tag: String,
    signature: String,
    #[serde(default)]
    patient_ref: Option<String>,
}

#[derive(Debug)]
struct Authenticated {
    report_id: String,
    category: String,
    label: Option<String>,
}

fn die(msg: &str) -> ! {
    eprintln!("error: {msg}");
    process::exit(1);
}

fn load_policy(path: &Path) -> Policy {
    let raw = fs::read_to_string(path).unwrap_or_else(|e| die(&format!("read policy: {e}")));
    serde_json::from_str(&raw).unwrap_or_else(|e| die(&format!("parse policy: {e}")))
}

fn verify_signature(pub_pem: &[u8], message: &[u8], sig_b64: &str) -> bool {
    let sig = match B64.decode(sig_b64.as_bytes()) {
        Ok(v) => v,
        Err(_) => return false,
    };
    let pkey = match PKey::public_key_from_pem(pub_pem) {
        Ok(k) => k,
        Err(_) => return false,
    };
    let mut verifier = match Verifier::new(MessageDigest::sha256(), &pkey) {
        Ok(v) => v,
        Err(_) => return false,
    };
    if verifier.update(message).is_err() {
        return false;
    }
    verifier.verify(&sig).unwrap_or(false)
}

fn decrypt_label(dek: &[u8], nonce_b64: &str, ct_b64: &str, tag_b64: &str) -> Option<String> {
    let nonce = B64.decode(nonce_b64.as_bytes()).ok()?;
    let ct = B64.decode(ct_b64.as_bytes()).ok()?;
    let tag = B64.decode(tag_b64.as_bytes()).ok()?;
    if nonce.len() != 12 || tag.len() != 16 {
        return None;
    }
    let mut tag_arr = [0u8; 16];
    tag_arr.copy_from_slice(&tag);
    let pt = decrypt_aead(Cipher::aes_256_gcm(), dek, Some(&nonce), &[], &ct, &tag_arr).ok()?;
    String::from_utf8(pt).ok()
}

fn canonical_value(v: &Value) -> Value {
    match v {
        Value::Object(map) => {
            let mut ordered = Map::new();
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            for k in keys {
                ordered.insert(k.clone(), canonical_value(&map[k]));
            }
            Value::Object(ordered)
        }
        Value::Array(items) => Value::Array(items.iter().map(canonical_value).collect()),
        other => other.clone(),
    }
}

fn canonical_json(v: &Value) -> String {
    serde_json::to_string(&canonical_value(v)).expect("serialize canonical json")
}

fn sign_bytes(priv_pem: &[u8], data: &[u8]) -> String {
    let pkey = PKey::private_key_from_pem(priv_pem).unwrap_or_else(|e| die(&format!("load signing key: {e}")));
    let mut signer =
        Signer::new(MessageDigest::sha256(), &pkey).unwrap_or_else(|e| die(&format!("signer: {e}")));
    signer
        .update(data)
        .unwrap_or_else(|e| die(&format!("signer update: {e}")));
    let sig = signer
        .sign_to_vec()
        .unwrap_or_else(|e| die(&format!("sign: {e}")));
    B64.encode(sig)
}

fn write_sqlite(db_path: &Path, authenticated: &[Authenticated], attestation_bytes: &[u8], denied_count: usize) {
    if db_path.exists() {
        let _ = fs::remove_file(db_path);
    }
    let conn = Connection::open(db_path).unwrap_or_else(|e| die(&format!("open db: {e}")));
    conn.execute_batch(
        "CREATE TABLE authentications (
            report_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            label TEXT,
            verified INTEGER NOT NULL
        );
        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );",
    )
    .unwrap_or_else(|e| die(&format!("create schema: {e}")));

    {
        let mut stmt = conn
            .prepare(
                "INSERT INTO authentications (report_id, category, label, verified)
                 VALUES (?1, ?2, ?3, 1)",
            )
            .unwrap_or_else(|e| die(&format!("prepare insert: {e}")));
        for row in authenticated {
            stmt.execute(params![row.report_id, row.category, row.label])
                .unwrap_or_else(|e| die(&format!("insert row: {e}")));
        }
    }

    let digest = hash(MessageDigest::sha256(), attestation_bytes)
        .unwrap_or_else(|e| die(&format!("sha256: {e}")));
    let hex = digest.iter().map(|b| format!("{b:02x}")).collect::<String>();

    let meta = [
        ("attestation_sha256", hex),
        ("authenticated_count", authenticated.len().to_string()),
        ("denied_count", denied_count.to_string()),
    ];
    {
        let mut stmt = conn
            .prepare("INSERT INTO meta (key, value) VALUES (?1, ?2)")
            .unwrap_or_else(|e| die(&format!("prepare meta: {e}")));
        for (k, v) in meta {
            stmt.execute(params![k, v])
                .unwrap_or_else(|e| die(&format!("insert meta: {e}")));
        }
    }
}

fn main() {
    let sealed_dir = PathBuf::from("/app/data/sealed");
    let policy_path = PathBuf::from("/app/data/policy.json");
    let archive_pub_path = PathBuf::from("/app/data/keys/archive_verify.pub");
    let dek_path = PathBuf::from("/app/data/keys/label_dek.bin");
    let signing_key_path = PathBuf::from("/app/data/keys/registry_signing");
    let out_dir = PathBuf::from("/app/output");
    let attestation_path = out_dir.join("seal_attestation.json");
    let sig_path = out_dir.join("seal_attestation.sig");
    let db_path = out_dir.join("seal_authz.db");

    let dek = fs::read(&dek_path).unwrap_or_else(|e| die(&format!("read dek: {e}")));
    if dek.len() != 32 {
        die("label_dek.bin must be exactly 32 bytes");
    }

    fs::create_dir_all(&out_dir).unwrap_or_else(|e| die(&format!("mkdir output: {e}")));

    let policy = load_policy(&policy_path);
    let authorized_classes: BTreeSet<String> = policy.authorized_classes.into_iter().collect();
    let decrypt_for: BTreeSet<String> = policy.decrypt_plaintext_for.into_iter().collect();
    let archive_pub =
        fs::read(&archive_pub_path).unwrap_or_else(|e| die(&format!("read archive pub: {e}")));
    let signing_key =
        fs::read(&signing_key_path).unwrap_or_else(|e| die(&format!("read signing key: {e}")));

    let mut paths: Vec<PathBuf> = fs::read_dir(&sealed_dir)
        .unwrap_or_else(|e| die(&format!("read sealed dir: {e}")))
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().and_then(|s| s.to_str()) == Some("json"))
        .collect();
    paths.sort();

    let mut authenticated: Vec<Authenticated> = Vec::new();
    let mut denied: Vec<String> = Vec::new();
    let scanned = paths.len();

    for path in paths {
        let raw = fs::read_to_string(&path).unwrap_or_else(|e| die(&format!("read {}: {e}", path.display())));
        let claim: Claim =
            serde_json::from_str(&raw).unwrap_or_else(|e| die(&format!("parse {}: {e}", path.display())));

        let msg = format!(
            "{}|{}|{}|{}|{}",
            claim.report_id, claim.category, claim.label_ciphertext, claim.label_nonce, claim.label_tag
        );

        let sig_ok = verify_signature(&archive_pub, msg.as_bytes(), &claim.signature);
        let class_ok = authorized_classes.contains(&claim.category);

        if !sig_ok || !class_ok {
            denied.push(claim.report_id);
            continue;
        }

        let label = if decrypt_for.contains(&claim.category) {
            match decrypt_label(&dek, &claim.label_nonce, &claim.label_ciphertext, &claim.label_tag) {
                Some(pt) => Some(pt),
                None => {
                    denied.push(claim.report_id);
                    continue;
                }
            }
        } else {
            None
        };

        let _ = claim.patient_ref;

        authenticated.push(Authenticated {
            report_id: claim.report_id,
            category: claim.category,
            label,
        });
    }

    denied.sort();

    let mut by_cat: BTreeMap<String, Vec<Authenticated>> = BTreeMap::new();
    for row in &authenticated {
        by_cat
            .entry(row.category.clone())
            .or_default()
            .push(Authenticated {
                report_id: row.report_id.clone(),
                category: row.category.clone(),
                label: row.label.clone(),
            });
    }

    let mut authorized = Vec::new();
    for (category, mut rows) in by_cat {
        rows.sort_by(|a, b| a.report_id.cmp(&b.report_id));
        let report_ids: Vec<Value> = rows
            .iter()
            .map(|r| Value::String(r.report_id.clone()))
            .collect();

        let mut obj = Map::new();
        obj.insert("category".into(), Value::String(category.clone()));
        obj.insert("report_ids".into(), Value::Array(report_ids));

        if decrypt_for.contains(&category) {
            let mut labels = Map::new();
            for r in &rows {
                if let Some(ref lab) = r.label {
                    labels.insert(r.report_id.clone(), Value::String(lab.clone()));
                }
            }
            obj.insert("labels".into(), Value::Object(labels));
        }
        authorized.push(Value::Object(obj));
    }

    let attestation = json!({
        "version": 1,
        "authorized": authorized,
        "denied": denied,
        "audit": {
            "scanned": scanned,
            "authenticated": authenticated.len(),
            "denied": denied.len(),
        }
    });

    let attestation_text = canonical_json(&attestation);
    let attestation_bytes = attestation_text.as_bytes();

    fs::write(&attestation_path, attestation_bytes)
        .unwrap_or_else(|e| die(&format!("write attestation: {e}")));

    let sig_b64 = sign_bytes(&signing_key, attestation_bytes);
    let mut sig_file = fs::File::create(&sig_path).unwrap_or_else(|e| die(&format!("write sig: {e}")));
    write!(sig_file, "{sig_b64}").unwrap_or_else(|e| die(&format!("write sig body: {e}")));

    write_sqlite(&db_path, &authenticated, attestation_bytes, denied.len());
}
RS

cd "$ROOT"
cargo build --release --offline --locked
install -m 0755 "$ROOT/target/release/seal_authz" /app/bin/seal_authz

# Enforce authn/authz against the seeded sealed claims
/app/bin/seal_authz
