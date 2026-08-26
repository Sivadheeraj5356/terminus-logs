mod extractor;

fn main() {
    if let Err(error) = extractor::run(std::env::args_os().skip(1).collect()) {
        eprintln!("rejected: {error}");
        std::process::exit(2);
    }
}
