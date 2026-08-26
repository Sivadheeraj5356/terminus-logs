use std::io::{self, Read};

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    let mut total = 0i32;
    let mut critical = 0i32;
    let mut major = 0i32;
    let mut delegated = false;
    let mut _stagnation = 0i32;
    for line in input.lines() {
        if let Some(v) = line.strip_prefix("axis=") {
            total += v.parse::<i32>().unwrap_or(0);
        } else if let Some(v) = line.strip_prefix("critical=") {
            critical = v.parse::<i32>().unwrap_or(0);
        } else if let Some(v) = line.strip_prefix("major=") {
            major = v.parse::<i32>().unwrap_or(0);
        } else if let Some(v) = line.strip_prefix("delegated=") {
            delegated = v == "true";
        } else if let Some(v) = line.strip_prefix("stagnation=") {
            _stagnation = v.parse::<i32>().unwrap_or(0);
        }
    }
    let mut index = 50 + total * 4 - critical * 18 - major * 7;
    if !delegated {
        index -= 25;
    }
    index = index.clamp(0, 100);
    let label = if index >= 82 {
        "strong"
    } else if index >= 62 {
        "guarded"
    } else {
        "fragile"
    };
    println!("{} {}", index, label);
}
