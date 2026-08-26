use std::env;

pub fn run_cli() -> i32 {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        return 1;
    }
    let sector = args[2].parse::<u64>().unwrap_or(0);
    if sector == 0 {
        0
    } else {
        1
    }
}
