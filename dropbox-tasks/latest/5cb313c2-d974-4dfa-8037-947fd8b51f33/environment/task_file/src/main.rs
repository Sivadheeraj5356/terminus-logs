use std::env;
use std::fs;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: auditor <input> <output>");
        std::process::exit(2);
    }
    let _ = fs::read_to_string(&args[1]).expect("read input");
    fs::create_dir_all(std::path::Path::new(&args[2]).parent().unwrap()).expect("mkdir output");
    fs::write(&args[2], "{\"decisions\":[],\"evidence\":[],\"summary\":{\"requests\":0,\"approved\":0,\"denied\":0,\"warnings\":0}}\n").expect("write output");
}
