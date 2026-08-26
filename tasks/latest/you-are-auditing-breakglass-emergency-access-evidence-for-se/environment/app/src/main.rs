mod ledger_seed;

const DEFAULT_OUTPUT: &str = "/app/output_data/breakglass_ledger.json";

fn initial_ledger_package() -> String {
    [
        "{",
        "\"ledger_entries\":[],",
        "\"severity_index\":{\"critical\":0,\"high\":0,\"medium\":0,\"low\":0}",
        "}\n",
    ]
    .join("")
}

fn main() {
    let _evidence = ledger_seed::default_evidence_names();
    let output_path = std::env::var("BREAKGLASS_OUT").unwrap_or_else(|_| DEFAULT_OUTPUT.to_string());
    if let Some(parent) = std::path::Path::new(&output_path).parent() {
        std::fs::create_dir_all(parent).unwrap();
    }
    std::fs::write(output_path, initial_ledger_package()).unwrap();
}
