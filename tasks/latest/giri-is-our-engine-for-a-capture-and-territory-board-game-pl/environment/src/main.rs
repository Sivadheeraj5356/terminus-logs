mod board;
mod notation;
mod rules;
mod score;
mod store;

use std::collections::BTreeMap;
use std::fs;
use std::process::Command;

use board::Board;

fn flags(args: &[String]) -> BTreeMap<String, String> {
    let mut m = BTreeMap::new();
    let mut i = 0;
    while i < args.len() {
        if let Some(key) = args[i].strip_prefix("--") {
            let val = args.get(i + 1).cloned().unwrap_or_default();
            m.insert(key.to_string(), val);
            i += 2;
        } else {
            i += 1;
        }
    }
    m
}

fn get<'a>(m: &'a BTreeMap<String, String>, k: &str) -> Result<&'a String, String> {
    m.get(k).ok_or_else(|| format!("missing --{k}"))
}

fn load_board(m: &BTreeMap<String, String>) -> Result<Board, String> {
    let path = get(m, "board")?;
    let text = fs::read_to_string(path).map_err(|e| format!("read board: {e}"))?;
    Board::parse(&text)
}

fn cmd_replay(m: &BTreeMap<String, String>) -> Result<(), String> {
    let brd = load_board(m)?;
    let dir = get(m, "games")?;
    let db = get(m, "db")?;
    let mut paths: Vec<_> = fs::read_dir(dir)
        .map_err(|e| format!("read games dir: {e}"))?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().map(|x| x == "log").unwrap_or(false))
        .collect();
    paths.sort();
    let mut rows = Vec::new();
    for p in paths {
        let gid = p.file_stem().unwrap().to_string_lossy().to_string();
        let text = fs::read_to_string(&p).map_err(|e| format!("read {gid}: {e}"))?;
        let moves = notation::parse_log(&text, &brd)
            .map_err(|e| format!("malformed log {gid}: {e}"))?;
        let oc = rules::replay(&moves, &brd);
        let (bs, ws) = score::area_score(&oc.state, &brd);
        rows.push(store::Row {
            game_id: gid,
            first_illegal: oc.first_illegal,
            reason: oc.reason,
            black_score: bs,
            white_score: ws,
            black_captures: oc.black_captures,
            white_captures: oc.white_captures,
            moves_played: oc.moves_played,
            final_board: rules::canonical(&oc.state, &brd),
        });
    }
    store::write_rows(db, &rows)
}

fn cmd_graph(m: &BTreeMap<String, String>) -> Result<(), String> {
    let brd = load_board(m)?;
    let db = get(m, "db")?;
    let game = get(m, "game")?;
    let dot_path = get(m, "dot")?;
    let svg_path = get(m, "svg")?;
    let sql = format!("SELECT final_board FROM games WHERE game_id='{}';", game.replace('\'', "''"));
    let rows = store::query(db, &sql)?;
    if rows.is_empty() || rows[0].is_empty() {
        return Err(format!("game {game} not found in store"));
    }
    let state = score::parse_board_str(&rows[0][0], &brd);
    let dot = score::dot(&state, &brd);
    fs::write(dot_path, &dot).map_err(|e| format!("write dot: {e}"))?;
    let out = Command::new("dot")
        .arg("-Tsvg")
        .arg(dot_path)
        .arg("-o")
        .arg(svg_path)
        .output()
        .map_err(|e| format!("run dot: {e}"))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).to_string());
    }
    Ok(())
}

fn cmd_report(m: &BTreeMap<String, String>) -> Result<(), String> {
    let db = get(m, "db")?;
    let game = get(m, "game")?;
    let sql = format!(
        "SELECT game_id,first_illegal,reason,black_score,white_score,black_captures,white_captures,moves_played,final_board FROM games WHERE game_id='{}';",
        game.replace('\'', "''")
    );
    let rows = store::query(db, &sql)?;
    if rows.is_empty() || rows[0].len() < 9 {
        return Err(format!("game {game} not found in store"));
    }
    let r = &rows[0];
    println!(
        "{{\"game_id\":\"{}\",\"first_illegal\":{},\"reason\":\"{}\",\"black_score\":{},\"white_score\":{},\"black_captures\":{},\"white_captures\":{},\"moves_played\":{},\"final_board\":\"{}\"}}",
        r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]
    );
    Ok(())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: giri <replay|graph|report> [flags]");
        std::process::exit(2);
    }
    let m = flags(&args[2..]);
    let res = match args[1].as_str() {
        "replay" => cmd_replay(&m),
        "graph" => cmd_graph(&m),
        "report" => cmd_report(&m),
        other => Err(format!("unknown subcommand {other}")),
    };
    if let Err(e) = res {
        eprintln!("giri: {e}");
        std::process::exit(2);
    }
}
