//! Generate ABI descriptor, C header, and package declaration lists from the IDL.
//!
//! Usage: idlgen --idl <path> --out-dir <dir>
//! Prints the ABI fingerprint (hex) to stdout. All output is a pure function of
//! the IDL content, so repeated runs on the same input are byte-identical.

use std::fs;
use std::path::PathBuf;
use std::process::exit;

fn arg_value(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

fn symbol_for(op: &str) -> String {
    format!("vellum_{op}")
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let idl_path = match arg_value(&args, "--idl") {
        Some(p) => PathBuf::from(p),
        None => {
            eprintln!("idlgen: --idl required");
            exit(2);
        }
    };
    let out_dir = match arg_value(&args, "--out-dir") {
        Some(p) => PathBuf::from(p),
        None => {
            eprintln!("idlgen: --out-dir required");
            exit(2);
        }
    };

    let text = fs::read_to_string(&idl_path).unwrap_or_else(|e| {
        eprintln!("idlgen: cannot read {}: {e}", idl_path.display());
        exit(1);
    });
    let descriptor = ffi_model::parse_idl(&text).unwrap_or_else(|e| {
        eprintln!("idlgen: {e}");
        exit(1);
    });

    fs::create_dir_all(&out_dir).unwrap();

    let abi_json = descriptor.canonical_json();
    fs::write(out_dir.join("abi.json"), abi_json.as_bytes()).unwrap();

    let mut ops = descriptor.operations.clone();
    ops.sort_by(|a, b| a.name.cmp(&b.name));

    let mut header = String::new();
    header.push_str("/* generated from interface/document.idl */\n");
    header.push_str("#ifndef VELLUM_DOCUMENT_H\n#define VELLUM_DOCUMENT_H\n");
    header.push_str("char *vellum_identity_json(void);\n");
    for op in &ops {
        header.push_str(&format!(
            "char *{}(const char *input); /* requires {} */\n",
            symbol_for(&op.name),
            op.requires
        ));
    }
    header.push_str("void vellum_free(char *ptr);\n");
    header.push_str("#endif\n");
    fs::write(out_dir.join("document.h"), header.as_bytes()).unwrap();

    let mut decls = String::new();
    for op in &ops {
        decls.push_str(&symbol_for(&op.name));
        decls.push('\n');
    }
    fs::write(out_dir.join("python_decl.txt"), decls.as_bytes()).unwrap();
    fs::write(out_dir.join("node_decl.txt"), decls.as_bytes()).unwrap();

    println!("{}", descriptor.fingerprint());
}
