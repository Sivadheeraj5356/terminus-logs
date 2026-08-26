#!/bin/bash
set -euo pipefail

cd /app
if [ -f "$HOME/.cargo/env" ]; then . "$HOME/.cargo/env"; fi

cat > /app/src/board.rs <<'GIRI_EOF'
use std::collections::BTreeMap;

pub struct Board {
    pub names: Vec<String>,
    pub index: BTreeMap<String, usize>,
    pub adj: Vec<Vec<usize>>,
}

impl Board {
    pub fn parse(text: &str) -> Result<Board, String> {
        let mut set: BTreeMap<String, ()> = BTreeMap::new();
        let mut edges: Vec<(String, String)> = Vec::new();
        for raw in text.lines() {
            let line = raw.split('#').next().unwrap().trim();
            if line.is_empty() {
                continue;
            }
            let parts: Vec<&str> = line.split_whitespace().collect();
            match parts.as_slice() {
                ["node", name] => {
                    set.insert((*name).to_string(), ());
                }
                ["edge", a, b] => {
                    edges.push(((*a).to_string(), (*b).to_string()));
                }
                _ => return Err(format!("malformed board line: {line}")),
            }
        }
        let names: Vec<String> = set.keys().cloned().collect();
        let mut index = BTreeMap::new();
        for (i, n) in names.iter().enumerate() {
            index.insert(n.clone(), i);
        }
        let mut adj: Vec<Vec<usize>> = vec![Vec::new(); names.len()];
        for (a, b) in edges {
            let ia = *index.get(&a).ok_or_else(|| format!("edge unknown node {a}"))?;
            let ib = *index.get(&b).ok_or_else(|| format!("edge unknown node {b}"))?;
            if ia == ib {
                return Err("self loop".to_string());
            }
            if !adj[ia].contains(&ib) {
                adj[ia].push(ib);
            }
            if !adj[ib].contains(&ia) {
                adj[ib].push(ia);
            }
        }
        for v in adj.iter_mut() {
            v.sort_unstable();
        }
        Ok(Board { names, index, adj })
    }

    pub fn n(&self) -> usize {
        self.names.len()
    }
}
GIRI_EOF

cat > /app/src/rules.rs <<'GIRI_EOF'
use std::collections::{BTreeSet, VecDeque};

use crate::board::Board;
use crate::notation::Move;

pub const EMPTY: u8 = 0;
pub const BLACK: u8 = 1;
pub const WHITE: u8 = 2;

pub struct Outcome {
    pub first_illegal: i64,
    pub reason: String,
    pub state: Vec<u8>,
    pub black_captures: u64,
    pub white_captures: u64,
    pub moves_played: u64,
}

// Iterative flood fill over same-value nodes; safe for large groups.
pub fn component(start: usize, want: u8, state: &[u8], board: &Board) -> Vec<usize> {
    let mut seen = vec![false; state.len()];
    let mut out = Vec::new();
    let mut q = VecDeque::new();
    seen[start] = true;
    q.push_back(start);
    while let Some(cur) = q.pop_front() {
        out.push(cur);
        for &nb in &board.adj[cur] {
            if !seen[nb] && state[nb] == want {
                seen[nb] = true;
                q.push_back(nb);
            }
        }
    }
    out
}

pub fn liberties(group: &[usize], state: &[u8], board: &Board) -> usize {
    let mut libs = vec![false; state.len()];
    let mut count = 0;
    for &n in group {
        for &nb in &board.adj[n] {
            if state[nb] == EMPTY && !libs[nb] {
                libs[nb] = true;
                count += 1;
            }
        }
    }
    count
}

fn opponent_dead(state: &[u8], opp: u8, board: &Board) -> Vec<usize> {
    let mut seen = vec![false; state.len()];
    let mut dead = Vec::new();
    for i in 0..state.len() {
        if state[i] == opp && !seen[i] {
            let grp = component(i, opp, state, board);
            for &g in &grp {
                seen[g] = true;
            }
            if liberties(&grp, state, board) == 0 {
                dead.extend_from_slice(&grp);
            }
        }
    }
    dead
}

pub fn canonical(state: &[u8], board: &Board) -> String {
    let mut s = String::new();
    for i in 0..state.len() {
        if i > 0 {
            s.push(';');
        }
        let c = match state[i] {
            BLACK => 'B',
            WHITE => 'W',
            _ => '.',
        };
        s.push_str(&board.names[i]);
        s.push(':');
        s.push(c);
    }
    s
}

pub fn replay(moves: &[Move], board: &Board) -> Outcome {
    let mut state = vec![EMPTY; board.n()];
    let mut history: BTreeSet<Vec<u8>> = BTreeSet::new();
    history.insert(state.clone());
    let mut prev_pass = false;
    let mut first_illegal: i64 = -1;
    let mut reason = String::new();
    let mut black_cap: u64 = 0;
    let mut white_cap: u64 = 0;
    let mut played: u64 = 0;

    for (i, mv) in moves.iter().enumerate() {
        let color = if i % 2 == 0 { BLACK } else { WHITE };
        match *mv {
            Move::Pass => {
                played = (i as u64) + 1;
                if prev_pass {
                    break;
                }
                prev_pass = true;
            }
            Move::Play(node) => {
                if state[node] != EMPTY {
                    first_illegal = i as i64;
                    reason = "occupied".to_string();
                    break;
                }
                state[node] = color;
                let opp = if color == BLACK { WHITE } else { BLACK };
                let dead = opponent_dead(&state, opp, board);
                for &d in &dead {
                    state[d] = EMPTY;
                }
                let removed = dead.len() as u64;
                let placed = component(node, color, &state, board);
                if liberties(&placed, &state, board) == 0 && removed == 0 {
                    state[node] = EMPTY;
                    first_illegal = i as i64;
                    reason = "suicide".to_string();
                    break;
                }
                if history.contains(&state) {
                    for &d in &dead {
                        state[d] = opp;
                    }
                    state[node] = EMPTY;
                    first_illegal = i as i64;
                    reason = "superko".to_string();
                    break;
                }
                history.insert(state.clone());
                if color == BLACK {
                    black_cap += removed;
                } else {
                    white_cap += removed;
                }
                prev_pass = false;
                played = (i as u64) + 1;
            }
        }
    }

    Outcome {
        first_illegal,
        reason,
        state,
        black_captures: black_cap,
        white_captures: white_cap,
        moves_played: played,
    }
}
GIRI_EOF

cat > /app/src/score.rs <<'GIRI_EOF'
use std::collections::BTreeSet;

use crate::board::Board;
use crate::rules::{component, BLACK, EMPTY, WHITE};

pub fn area_score(state: &[u8], board: &Board) -> (u64, u64) {
    let mut black = state.iter().filter(|&&c| c == BLACK).count() as u64;
    let mut white = state.iter().filter(|&&c| c == WHITE).count() as u64;
    let mut seen = vec![false; state.len()];
    for i in 0..state.len() {
        if state[i] == EMPTY && !seen[i] {
            let region = component(i, EMPTY, state, board);
            let mut border: BTreeSet<u8> = BTreeSet::new();
            for &r in &region {
                seen[r] = true;
                for &nb in &board.adj[r] {
                    if state[nb] != EMPTY {
                        border.insert(state[nb]);
                    }
                }
            }
            if border.len() == 1 {
                if border.contains(&BLACK) {
                    black += region.len() as u64;
                } else {
                    white += region.len() as u64;
                }
            }
        }
    }
    (black, white)
}

pub struct Comp {
    pub kind: &'static str,
    pub color: &'static str,
    pub members: Vec<usize>,
}

pub fn components(state: &[u8], board: &Board) -> Vec<Comp> {
    let mut seen = vec![false; state.len()];
    let mut comps = Vec::new();
    for i in 0..state.len() {
        if seen[i] {
            continue;
        }
        let color = state[i];
        let mut members = component(i, color, state, board);
        members.sort_unstable();
        for &m in &members {
            seen[m] = true;
        }
        let kind = if color == EMPTY { "region" } else { "group" };
        let col = match color {
            BLACK => "black",
            WHITE => "white",
            _ => "empty",
        };
        comps.push(Comp { kind, color: col, members });
    }
    comps.sort_by(|a, b| a.members.cmp(&b.members));
    comps
}

pub fn dot(state: &[u8], board: &Board) -> String {
    let comps = components(state, board);
    let mut of = vec![0usize; state.len()];
    for (ci, c) in comps.iter().enumerate() {
        for &m in &c.members {
            of[m] = ci;
        }
    }
    let mut out = String::from("graph giri {\n");
    for (ci, c) in comps.iter().enumerate() {
        let members: Vec<&str> = c.members.iter().map(|&m| board.names[m].as_str()).collect();
        out.push_str(&format!(
            "  c{ci} [kind=\"{}\" color=\"{}\" size=\"{}\" members=\"{}\"];\n",
            c.kind,
            c.color,
            c.members.len(),
            members.join(" ")
        ));
    }
    let mut edges: BTreeSet<(usize, usize)> = BTreeSet::new();
    for a in 0..state.len() {
        for &b in &board.adj[a] {
            if of[a] != of[b] {
                let lo = of[a].min(of[b]);
                let hi = of[a].max(of[b]);
                edges.insert((lo, hi));
            }
        }
    }
    for (lo, hi) in edges {
        out.push_str(&format!("  c{lo} -- c{hi};\n"));
    }
    out.push_str("}\n");
    out
}

pub fn parse_board_str(s: &str, board: &Board) -> Vec<u8> {
    let mut state = vec![EMPTY; board.n()];
    for tok in s.split(';') {
        let mut it = tok.split(':');
        let name = it.next().unwrap_or("");
        let col = it.next().unwrap_or(".");
        if let Some(&i) = board.index.get(name) {
            state[i] = match col {
                "B" => BLACK,
                "W" => WHITE,
                _ => EMPTY,
            };
        }
    }
    state
}
GIRI_EOF

cat > /app/src/store.rs <<'GIRI_EOF'
use std::io::Write;
use std::process::{Command, Stdio};

pub struct Row {
    pub game_id: String,
    pub first_illegal: i64,
    pub reason: String,
    pub black_score: u64,
    pub white_score: u64,
    pub black_captures: u64,
    pub white_captures: u64,
    pub moves_played: u64,
    pub final_board: String,
}

fn esc(s: &str) -> String {
    s.replace('\'', "''")
}

pub const SCHEMA: &str = "\
CREATE TABLE IF NOT EXISTS games (
  game_id TEXT PRIMARY KEY,
  first_illegal INTEGER NOT NULL,
  reason TEXT NOT NULL,
  black_score INTEGER NOT NULL,
  white_score INTEGER NOT NULL,
  black_captures INTEGER NOT NULL,
  white_captures INTEGER NOT NULL,
  moves_played INTEGER NOT NULL,
  final_board TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS superko_sites (
  game_id TEXT NOT NULL,
  move_index INTEGER NOT NULL
);
";

pub fn run_sql(db: &str, sql: &str) -> Result<(), String> {
    let mut child = Command::new("sqlite3")
        .arg(db)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("spawn sqlite3: {e}"))?;
    child
        .stdin
        .as_mut()
        .unwrap()
        .write_all(sql.as_bytes())
        .map_err(|e| format!("write sqlite3: {e}"))?;
    let out = child.wait_with_output().map_err(|e| format!("{e}"))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).to_string());
    }
    Ok(())
}

pub fn write_rows(db: &str, rows: &[Row]) -> Result<(), String> {
    let mut sql = String::new();
    sql.push_str(SCHEMA);
    sql.push_str("DELETE FROM games;\nDELETE FROM superko_sites;\n");
    sql.push_str("BEGIN;\n");
    // deterministic order
    let mut ordered: Vec<&Row> = rows.iter().collect();
    ordered.sort_by(|a, b| a.game_id.cmp(&b.game_id));
    for r in ordered {
        sql.push_str(&format!(
            "INSERT INTO games VALUES ('{}',{},'{}',{},{},{},{},{},'{}');\n",
            esc(&r.game_id),
            r.first_illegal,
            esc(&r.reason),
            r.black_score,
            r.white_score,
            r.black_captures,
            r.white_captures,
            r.moves_played,
            esc(&r.final_board),
        ));
        if r.reason == "superko" {
            sql.push_str(&format!(
                "INSERT INTO superko_sites VALUES ('{}',{});\n",
                esc(&r.game_id),
                r.first_illegal
            ));
        }
    }
    sql.push_str("COMMIT;\n");
    run_sql(db, &sql)
}

pub fn query(db: &str, sql: &str) -> Result<Vec<Vec<String>>, String> {
    let out = Command::new("sqlite3")
        .arg("-separator")
        .arg("\u{1f}")
        .arg(db)
        .arg(sql)
        .output()
        .map_err(|e| format!("query sqlite3: {e}"))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).to_string());
    }
    let text = String::from_utf8_lossy(&out.stdout);
    let mut rows = Vec::new();
    for line in text.lines() {
        rows.push(line.split('\u{1f}').map(|s| s.to_string()).collect());
    }
    Ok(rows)
}
GIRI_EOF

export CARGO_NET_OFFLINE=true
cargo build --release --offline
