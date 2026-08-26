mod adjudication;
mod briefing;
mod composition;
mod decoy;
mod state;
fn main() {
    if let Err(e) = dispatch() {
        let input = e.starts_with("INPUT");
        eprintln!("ERROR {}", e);
        std::process::exit(if input { 2 } else { 1 })
    }
}
fn dispatch() -> Result<(), String> {
    let a = std::env::args().collect::<Vec<_>>();
    match a.get(1).map(String::as_str) {
        Some("adjudicate") => {
            let mut obs = None;
            let mut policy = None;
            let mut i = 2;
            while i + 1 < a.len() {
                match a[i].as_str() {
                    "--observations" => obs = Some(a[i + 1].clone()),
                    "--policy" => policy = Some(a[i + 1].clone()),
                    _ => return Err("INPUT arguments".into()),
                }
                i += 2
            }
            adjudication::ingest_observations(
                &obs.ok_or("INPUT observations argument")?,
                &policy.ok_or("INPUT policy argument")?,
            )
        }
        Some("compose") => composition::compose_constellation(),
        Some("brief") => briefing::export_brief(),
        _ => Err("INPUT command".into()),
    }
}
