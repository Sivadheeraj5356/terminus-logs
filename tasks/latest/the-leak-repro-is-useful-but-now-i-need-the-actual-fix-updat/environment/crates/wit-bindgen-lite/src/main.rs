use std::env;
use std::fs;
use std::path::Path;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 5 {
        eprintln!("usage: wit-bindgen-lite <wit> <generated-rs> <metadata-json> <wasm-out>");
        std::process::exit(2);
    }

    let wit_path = Path::new(&args[1]);
    let generated_path = Path::new(&args[2]);
    let metadata_path = Path::new(&args[3]);
    let wasm_path = Path::new(&args[4]);

    let wit = fs::read_to_string(wit_path).expect("read WIT");
    if !wit.contains("wasi:io/streams") {
        eprintln!("worker.wit must import wasi:io/streams");
        std::process::exit(3);
    }

    if let Some(parent) = generated_path.parent() {
        fs::create_dir_all(parent).expect("create generated parent");
    }
    fs::write(
        generated_path,
        "pub const BINDING_TOOL: &str = \"wit-bindgen-lite\";\n\
         pub const STREAM_INTERFACE: &str = \"wasi:io/streams\";\n\
         pub const WORLD: &str = \"edge-worker\";\n",
    )
    .expect("write generated bindings");

    if let Some(parent) = metadata_path.parent() {
        fs::create_dir_all(parent).expect("create metadata parent");
    }
    fs::write(
        metadata_path,
        "{\n  \"binding_tool\": \"wit-bindgen-lite\",\n  \"interface\": \"wasi:io/streams\",\n  \"world\": \"edge-worker\"\n}\n",
    )
    .expect("write build metadata");

    if let Some(parent) = wasm_path.parent() {
        fs::create_dir_all(parent).expect("create wasm parent");
    }
    let mut wasm = b"\0asm\x01\0\0\0".to_vec();
    wasm.extend_from_slice(b"telemetry-edge-worker-preview2-component");
    wasm.extend_from_slice(wit.as_bytes());
    fs::write(wasm_path, wasm).expect("write wasm artifact");
}
