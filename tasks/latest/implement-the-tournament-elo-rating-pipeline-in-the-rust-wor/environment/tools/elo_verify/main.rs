use std::env; use std::fs; use std::process;
use match_parser::parse_matches;
use rating_engine::calculate_elo;
use kfactor_calculator::analyze_kfactor;
use leaderboard::generate_leaderboard;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("Usage: elo_verify <input> <output>");
        process::exit(1);
    }
    
    let data = match fs::read_to_string(&args[1]) {
        Ok(d) => d,
        Err(e) => { eprintln!("Error: {}", e); process::exit(1); }
    };
    
    let matches = parse_matches(&data);
    if matches.is_empty() {
        eprintln!("No matches");
        process::exit(1);
    }
    
    let elo = calculate_elo(&matches);
    let analysis = analyze_kfactor(&elo);
    let report = generate_leaderboard(&analysis);
    
    let output = serde_json::to_string_pretty(&report).unwrap();
    fs::write(&args[2], output).unwrap();
}
