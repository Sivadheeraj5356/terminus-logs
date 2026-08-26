mod args;
mod emit;

use args::parse;
use emit::write_record;
use v7::{badge, digest_hex, mark_plane, mark_point, tally_line};
use k3::{fmt_grid, Grid, Tone};
use s2::{caption, meta_tag, restore_marks, EV_CLEAR, EV_PLACE};
use std::env;
use std::fs;
use std::path::PathBuf;

#[derive(Clone)]
struct MoveSpec {
    q: i32,
    r: i32,
    tone: Tone,
}

#[derive(Clone)]
struct Scenario {
    id: String,
    seed: u64,
    mode: String,
    w: i32,
    h: i32,
    moves: Vec<MoveSpec>,
    journal_prefix: usize,
}

fn parse_tone(s: &str) -> Result<Tone, String> {
    match s {
        "dark" | "x" => Ok(Tone::Dark),
        "light" | "o" => Ok(Tone::Light),
        _ => Err(format!("bad tone {}", s)),
    }
}

fn parse_scenario(path: &str) -> Result<Scenario, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut id = String::new();
    let mut seed = 1u64;
    let mut mode = "flat".to_string();
    let mut w = 5i32;
    let mut h = 5i32;
    let mut moves = Vec::new();
    let mut journal_prefix = 0usize;
    let mut in_moves = false;
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if line == "[[moves]]" {
            in_moves = true;
            continue;
        }
        if !in_moves {
            if let Some(rest) = line.strip_prefix("id = ") {
                id = rest.trim().trim_matches('"').to_string();
            } else if let Some(rest) = line.strip_prefix("seed = ") {
                seed = rest.trim().parse().map_err(|_| "bad seed")?;
            } else if let Some(rest) = line.strip_prefix("mode = ") {
                mode = rest.trim().trim_matches('"').to_string();
            } else if let Some(rest) = line.strip_prefix("w = ") {
                w = rest.trim().parse().map_err(|_| "bad w")?;
            } else if let Some(rest) = line.strip_prefix("h = ") {
                h = rest.trim().parse().map_err(|_| "bad h")?;
            } else if let Some(rest) = line.strip_prefix("journal_prefix = ") {
                journal_prefix = rest.trim().parse().map_err(|_| "bad journal_prefix")?;
            }
        } else if let Some(rest) = line.strip_prefix("move = ") {
            let inner = rest.trim().trim_matches('"');
            let parts: Vec<_> = inner.split(',').collect();
            if parts.len() != 3 {
                return Err("move needs q,r,tone".into());
            }
            moves.push(MoveSpec {
                q: parts[0].parse().map_err(|_| "bad q")?,
                r: parts[1].parse().map_err(|_| "bad r")?,
                tone: parse_tone(parts[2])?,
            });
        }
    }
    if id.is_empty() {
        id = PathBuf::from(path)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("run")
            .to_string();
    }
    Ok(Scenario {
        id,
        seed,
        mode,
        w,
        h,
        moves,
        journal_prefix,
    })
}

#[derive(Clone)]
struct RunState {
    grid: Grid,
    history: Vec<[u8; 32]>,
    rejected: u32,
    event_bytes: Vec<u8>,
    stamps: Vec<(i32, i32, Tone)>,
    ko_ban: Option<[u8; 32]>,
}

fn point_mark(q: i32, r: i32, w: i32, h: i32) -> [u8; 32] {
    mark_point(q, r, w, h)
}

impl RunState {
    fn new(w: i32, h: i32, belt: bool) -> Self {
        Self {
            grid: Grid::new(w, h, belt),
            history: Vec::new(),
            rejected: 0,
            event_bytes: Vec::new(),
            stamps: Vec::new(),
            ko_ban: None,
        }
    }

    fn liberty_fingerprint(&self) -> u16 {
        let plane = self.grid.cells.len();
        let mut seen = vec![false; plane];
        let mut total = 0u16;
        for i in 0..plane {
            if seen[i] || self.grid.cells[i] == Tone::Void {
                continue;
            }
            let q = (i as i32) % self.grid.w;
            let r = (i as i32) / self.grid.w;
            let (stones, slots) = self.grid.cluster_slots(q, r);
            for &s in &stones {
                seen[s] = true;
            }
            let mut scratch = Vec::new();
            total = total.wrapping_add(k3::op_k3(&mut scratch, &slots, plane));
        }
        total
    }

    fn position_digest(&self) -> [u8; 32] {
        let packed = self.grid.pack_marks(&self.stamps);
        let mut dig = mark_plane(
            &packed,
            self.grid.w as u16,
            self.grid.h as u16,
        );
        let fp = self.liberty_fingerprint();
        dig[0] ^= (fp & 0xff) as u8;
        dig[1] ^= ((fp >> 8) & 0xff) as u8;
        dig
    }

    fn push_event(&mut self, kind: u8, dig: &[u8; 32]) {
        self.event_bytes.push(kind);
        self.event_bytes.extend_from_slice(dig);
    }

    fn rebuild_stamps(&mut self) {
        let mut preserved = Vec::new();
        let mut used = vec![false; self.stamps.len()];
        for r in 0..self.grid.h {
            for q in 0..self.grid.w {
                let t = self.grid.get(q, r);
                if t == Tone::Void {
                    continue;
                }
                let mut found = false;
                for (i, (sq, sr, st)) in self.stamps.iter().enumerate() {
                    if used[i] {
                        continue;
                    }
                    if *st == t && self.grid.norm(*sq, *sr) == Some((q, r)) {
                        preserved.push((*sq, *sr, t));
                        used[i] = true;
                        found = true;
                        break;
                    }
                }
                if !found {
                    preserved.push((q, r, t));
                }
            }
        }
        self.stamps = preserved;
    }
}

fn play_on_clone(base: &RunState, mv: &MoveSpec) -> Result<(RunState, bool), String> {
    let mut st = base.clone();
    let snapshot = st.clone();
    let Some((pq, pr)) = st.grid.norm(mv.q, mv.r) else {
        return Err("out of bounds".into());
    };
    if st.grid.get(pq, pr) != Tone::Void {
        return Err("occupied".into());
    }
    let place_key = point_mark(mv.q, mv.r, st.grid.w, st.grid.h);
    if st.ko_ban.as_ref() == Some(&place_key) {
        return Ok((snapshot, false));
    }

    st.grid.set(pq, pr, mv.tone);
    st.stamps.push((mv.q, mv.r, mv.tone));

    let opp = mv.tone.flip();
    let mut captured = Vec::new();
    let mut capture_cells: Vec<(i32, i32)> = Vec::new();
    for (nq, nr) in st.grid.neighbors(pq, pr) {
        if st.grid.get(nq, nr) == opp {
            let (stones, _slots) = st.grid.cluster_slots(nq, nr);
            let libs = st.grid.liberty_count(nq, nr);
            if libs == 0 {
                for &si in &stones {
                    let cq = (si as i32) % st.grid.w;
                    let cr = (si as i32) / st.grid.w;
                    capture_cells.push((cq, cr));
                }
                captured.extend(stones);
            }
        }
    }
    captured.sort_unstable();
    captured.dedup();
    capture_cells.sort_unstable();
    capture_cells.dedup();
    let had_clear = !captured.is_empty();
    if had_clear {
        st.grid.remove_cluster(&captured);
    }
    st.rebuild_stamps();

    let libs = st.grid.liberty_count(pq, pr);
    if libs == 0 {
        return Err("suicide".into());
    }

    let dig = st.position_digest();
    if st.history.iter().any(|h| h == &dig) {
        return Ok((snapshot, false));
    }

    if capture_cells.len() == 1 {
        let (cq, cr) = capture_cells[0];
        st.ko_ban = Some(point_mark(cq, cr, st.grid.w, st.grid.h));
    } else {
        st.ko_ban = None;
    }

    if had_clear {
        st.push_event(EV_CLEAR, &dig);
    } else {
        st.push_event(EV_PLACE, &dig);
    }
    st.history.push(dig);
    Ok((st, true))
}

fn record_json(id: &str, seed: u64, mode: &str, st: &RunState) -> String {
    let (dark, light) = st.grid.counts();
    let digests: Vec<String> = st.history.iter().map(digest_hex).collect();
    let terminal = digest_hex(&st.position_digest());
    let mut body = String::new();
    body.push_str("{\n");
    body.push_str(&format!("  \"scenario_id\": \"{}\",\n", id));
    body.push_str(&format!("  \"seed\": {},\n", seed));
    body.push_str(&format!("  \"mode\": \"{}\",\n", mode));
    body.push_str(&format!(
        "  \"final_counts\": {{\"dark\": {}, \"light\": {}}},\n",
        dark, light
    ));
    body.push_str(&format!("  \"history_len\": {},\n", st.history.len()));
    body.push_str(&format!("  \"rejected_repeats\": {},\n", st.rejected));
    body.push_str("  \"position_digests\": [");
    for (i, d) in digests.iter().enumerate() {
        if i > 0 {
            body.push_str(", ");
        }
        body.push_str(&format!("\"{}\"", d));
    }
    body.push_str("],\n");
    body.push_str(&format!("  \"terminal_digest\": \"{}\"\n", terminal));
    body.push_str("}\n");
    let _ = fmt_grid(&st.grid);
    let _ = meta_tag(id);
    let _ = caption(id, st.history.len());
    let _ = tally_line(st.history.len() as u32, st.rejected);
    let _ = badge(st.history.len() as u32);
    body
}

fn run_moves(st: &mut RunState, moves: &[MoveSpec]) -> Result<(), String> {
    for mv in moves {
        let (next, ok) = play_on_clone(st, mv)?;
        if ok {
            *st = next;
        } else {
            st.rejected += 1;
            // keep prior state; next already snapshot of prior
            let _ = next;
        }
    }
    Ok(())
}

fn main() {
    let argv: Vec<String> = env::args().collect();
    let opts = match parse(&argv) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("{}", e);
            std::process::exit(2);
        }
    };
    let result = (|| -> Result<(), String> {
        match opts.cmd.as_str() {
            "run" => {
                let name = opts.scenario.ok_or("run needs --scenario")?;
                let path = format!("/app/data/{}.toml", name);
                let mut sc = parse_scenario(&path)?;
                if let Some(s) = opts.seed {
                    sc.seed = s;
                }
                let belt = sc.mode == "belt";
                let mut st = RunState::new(sc.w, sc.h, belt);
                run_moves(&mut st, &sc.moves)?;
                let body = record_json(&sc.id, sc.seed, &sc.mode, &st);
                let out = PathBuf::from(&opts.out_dir).join(format!("{}.json", sc.id));
                write_record(&out, &body)?;
            }
            "resume" => {
                let journal = opts.journal.ok_or("resume needs --journal")?;
                let mut sc = parse_scenario(&journal)?;
                if let Some(s) = opts.seed {
                    sc.seed = s;
                }
                let tag = opts.tag.unwrap_or_else(|| "long_resume".into());
                let belt = sc.mode == "belt";
                let mut st = RunState::new(sc.w, sc.h, belt);
                let prefix = sc.journal_prefix.min(sc.moves.len());
                run_moves(&mut st, &sc.moves[..prefix])?;
                let packed = st.event_bytes.clone();
                let mut rebuilt = Vec::new();
                restore_marks(&mut rebuilt, &packed);
                st.history = rebuilt;
                run_moves(&mut st, &sc.moves[prefix..])?;
                let body = record_json(&tag, sc.seed, &sc.mode, &st);
                let out = PathBuf::from(&opts.out_dir).join(format!("{}.json", tag));
                write_record(&out, &body)?;
            }
            other => return Err(format!("unknown command {}", other)),
        }
        Ok(())
    })();
    if let Err(e) = result {
        eprintln!("{}", e);
        std::process::exit(1);
    }
}
