use std::env;
use std::fs;

fn main() {
    let args: Vec<String> = env::args().collect();
    let spec_path = &args[1];
    let out = &args[2];
    let text = fs::read_to_string(spec_path).unwrap();
    let n: usize = text.lines().next().unwrap().trim().parse().unwrap();
    let mut s = String::new();
    s.push_str("OPENQASM 3;\n");
    s.push_str("include \"stdgates.inc\";\n");
    s.push_str(&format!("qubit[{}] q;\n", n));
    fs::write(out, s).unwrap();
}
