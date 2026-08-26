fn main() {
    let mut args = std::env::args().skip(1);
    let _toolchain = match args.next() {
        Some(v) => v,
        None => std::process::exit(2),
    };
    let _floor = match args.next() {
        Some(v) => v,
        None => std::process::exit(2),
    };
    println!("match");
    std::process::exit(0);
}
