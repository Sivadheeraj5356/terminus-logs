#[tokio::main]
async fn main() {
    if let Err(err) = tzforge::cli::run(std::env::args().skip(1).collect()).await {
        eprintln!("tzforge: {err}");
        std::process::exit(1);
    }
}
