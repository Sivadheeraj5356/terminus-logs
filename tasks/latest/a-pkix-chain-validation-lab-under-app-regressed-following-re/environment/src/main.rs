fn main() {
    if let Err(e) = tb_cvrs::harness::drive() {
        eprintln!("harness: {}", e);
        std::process::exit(1);
    }
}
