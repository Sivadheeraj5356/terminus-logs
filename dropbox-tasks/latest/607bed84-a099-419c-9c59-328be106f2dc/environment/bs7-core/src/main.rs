use bs7_core::solve::solve;
use bs7_core::types::SolveIn;
use std::io::{self, Read};

fn main() {
    let mut buf = String::new();
    io::stdin().read_to_string(&mut buf).expect("stdin");
    let input: SolveIn = serde_json::from_str(&buf).expect("json");
    let out = solve(input);
    println!("{}", serde_json::to_string(&out).unwrap());
}
