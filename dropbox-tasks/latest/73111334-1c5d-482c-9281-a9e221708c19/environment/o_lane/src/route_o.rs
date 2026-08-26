pub fn route_o(suite: &str, ticks: u64) -> Vec<String> {
    vec![
        format!("DISPATCH:{suite}"),
        format!("PLAN:{ticks}"),
        "SEAL".to_string(),
    ]
}
