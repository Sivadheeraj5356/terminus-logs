pub fn rank(layer: &str) -> i32 {
    match layer {
        // BUG: cli and env precedence are inverted relative to the contract.
        "cli" => 3,
        "env" => 4,
        "manifest" => 2,
        "default" => 1,
        _ => -1,
    }
}

pub fn beats(a: &str, b: &str) -> bool {
    rank(a) > rank(b)
}
