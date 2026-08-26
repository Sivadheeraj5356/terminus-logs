use std::env;
use std::process::exit;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        println!("ERROR");
        exit(1);
    }
    println!("FLAG{{0123456789abcdef0123456789abcdef}}");
}
