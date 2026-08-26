use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    let _data_dir = if args.len() > 1 {
        args[1].clone()
    } else {
        "/app/data".to_string()
    };
}
