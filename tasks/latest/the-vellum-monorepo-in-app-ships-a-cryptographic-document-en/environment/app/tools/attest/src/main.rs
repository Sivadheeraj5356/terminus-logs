//! Build the canonical provenance manifest binding the final release artifacts.
//!
//! Usage:
//!   attest --identity <identity.json> --output-root <dir> \
//!          --subject <relpath> [--subject <relpath> ...] --out <provenance.json>
//!
//! Each subject is measured (size + sha256) from disk at the moment attest runs,
//! so the manifest reflects whatever bytes exist on disk when it is invoked.

use std::fs;
use std::path::PathBuf;
use std::process::exit;

use docmodel::{dump_compact, parse, sha256_hex, Value};

fn arg_value(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

fn arg_values(args: &[String], flag: &str) -> Vec<String> {
    let mut out = Vec::new();
    for (i, a) in args.iter().enumerate() {
        if a == flag {
            if let Some(v) = args.get(i + 1) {
                out.push(v.clone());
            }
        }
    }
    out
}

fn field<'a>(v: &'a Value, key: &str) -> &'a Value {
    v.get(key).unwrap_or(&Value::Null)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let identity_path = arg_value(&args, "--identity").unwrap_or_default();
    let output_root = PathBuf::from(arg_value(&args, "--output-root").unwrap_or_default());
    let out_path = PathBuf::from(arg_value(&args, "--out").unwrap_or_default());
    let subject_rels = arg_values(&args, "--subject");

    let identity_text = fs::read_to_string(&identity_path).unwrap_or_else(|e| {
        eprintln!("attest: cannot read identity {identity_path}: {e}");
        exit(1);
    });
    let identity = parse(&identity_text).unwrap_or_else(|e| {
        eprintln!("attest: bad identity json: {e}");
        exit(1);
    });

    let mut subjects: Vec<(String, i64, String)> = Vec::new();
    for rel in &subject_rels {
        let path = output_root.join(rel);
        let bytes = fs::read(&path).unwrap_or_else(|e| {
            eprintln!("attest: cannot read subject {}: {e}", path.display());
            exit(1);
        });
        subjects.push((rel.clone(), bytes.len() as i64, format!("sha256:{}", sha256_hex(&bytes))));
    }
    subjects.sort_by(|a, b| a.0.cmp(&b.0));

    let subject_values: Vec<Value> = subjects
        .into_iter()
        .map(|(path, size, sha)| {
            Value::Obj(vec![
                ("path".to_string(), Value::Str(path)),
                ("sha256".to_string(), Value::Str(sha)),
                ("size".to_string(), Value::Int(size)),
            ])
        })
        .collect();

    let runtime = Value::Obj(vec![
        ("abi_fingerprint".to_string(), field(&identity, "abi_fingerprint").clone()),
        ("capabilities".to_string(), field(&identity, "capabilities").clone()),
        (
            "dependency_closure_digest".to_string(),
            field(&identity, "dependency_closure_digest").clone(),
        ),
    ]);
    let source = Value::Obj(vec![
        ("revision".to_string(), field(&identity, "revision").clone()),
        ("version".to_string(), field(&identity, "version").clone()),
    ]);

    let provenance = Value::Obj(vec![
        ("release_id".to_string(), field(&identity, "release_id").clone()),
        ("runtime".to_string(), runtime),
        ("schema_version".to_string(), Value::Int(1)),
        ("source".to_string(), source),
        ("subjects".to_string(), Value::Arr(subject_values)),
    ]);

    let text = dump_compact(&provenance);
    fs::write(&out_path, text.as_bytes()).unwrap_or_else(|e| {
        eprintln!("attest: cannot write {}: {e}", out_path.display());
        exit(1);
    });
}
