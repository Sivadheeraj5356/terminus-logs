#!/bin/bash
set -euo pipefail
APP=/app
mkdir -p "$APP/src"
cat > "$APP/src/cli.rs" <<'RSXEOF'
use crate::dfa::{self};
use crate::minimize;
use crate::nfa;
use crate::parser;
use crate::scan;
use std::io::Write;

pub fn run(args: &[String]) -> i32 {
    if args.len() < 2 {
        eprintln!("usage: rsx <compile|scan> ...");
        return 2;
    }
    match args[1].as_str() {
        "compile" => run_compile(&args[2..]),
        "scan" => run_scan(&args[2..]),
        _ => {
            eprintln!("unknown subcommand");
            2
        }
    }
}

fn run_compile(args: &[String]) -> i32 {
    if args.len() != 1 {
        eprintln!("usage: rsx compile '<regex>'");
        return 2;
    }
    let pattern = args[0].as_bytes();
    let node = match parser::parse(pattern) {
        Ok(n) => n,
        Err(_) => return 1,
    };
    let (_astart, _aend, core) = parser::split_anchors(&node);
    let nfa = nfa::build(&core);
    let raw_dfa = dfa::subset_construct(&nfa);
    let min = minimize::minimize(&raw_dfa);
    let canon = dfa::prune_and_canonicalize(&min);
    let text = dfa::render(&canon);
    let stdout = std::io::stdout();
    let mut h = stdout.lock();
    let _ = h.write_all(text.as_bytes());
    0
}

fn run_scan(args: &[String]) -> i32 {
    let mut patterns_path: Option<String> = None;
    let mut input_path: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--patterns" => {
                if i + 1 >= args.len() {
                    return 2;
                }
                patterns_path = Some(args[i + 1].clone());
                i += 2;
            }
            "--input" => {
                if i + 1 >= args.len() {
                    return 2;
                }
                input_path = Some(args[i + 1].clone());
                i += 2;
            }
            _ => {
                eprintln!("unknown argument");
                return 2;
            }
        }
    }
    let patterns_path = match patterns_path {
        Some(p) => p,
        None => return 2,
    };
    let input_path = match input_path {
        Some(p) => p,
        None => return 2,
    };
    let patterns_raw = match std::fs::read(&patterns_path) {
        Ok(d) => d,
        Err(_) => return 2,
    };
    let input = match std::fs::read(&input_path) {
        Ok(d) => d,
        Err(_) => return 2,
    };

    let mut patterns: Vec<Vec<u8>> = Vec::new();
    for line in split_lines(&patterns_raw) {
        if line.is_empty() {
            continue;
        }
        patterns.push(line);
    }

    let mut items: Vec<(Vec<u8>, Vec<(usize, usize)>)> = Vec::new();
    for p in &patterns {
        let compiled = match scan::compile_pattern(p) {
            Ok(c) => c,
            Err(_) => return 1,
        };
        let spans = scan::scan_one(&compiled, &input);
        items.push((p.clone(), spans));
    }

    let text = scan::render_report(&items);
    let stdout = std::io::stdout();
    let mut h = stdout.lock();
    let _ = h.write_all(text.as_bytes());
    0
}

fn split_lines(data: &[u8]) -> Vec<Vec<u8>> {
    let mut out = Vec::new();
    let mut cur = Vec::new();
    for &b in data {
        if b == b'\n' {
            out.push(std::mem::take(&mut cur));
        } else if b == b'\r' {
            continue;
        } else {
            cur.push(b);
        }
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out
}
RSXEOF
cat > "$APP/src/scan.rs" <<'RSXEOF'
use crate::dfa::{self, Dfa};
use crate::minimize;
use crate::nfa;
use crate::parser;

pub struct Compiled {
    pub raw: Vec<u8>,
    pub dfa: Dfa,
    pub anchor_start: bool,
    pub anchor_end: bool,
}

pub fn compile_pattern(raw: &[u8]) -> Result<Compiled, String> {
    let node = parser::parse(raw)?;
    let (astart, aend, core) = parser::split_anchors(&node);
    let nfa = nfa::build(&core);
    let raw_dfa = dfa::subset_construct(&nfa);
    let min = minimize::minimize(&raw_dfa);
    let canon = dfa::prune_and_canonicalize(&min);
    Ok(Compiled {
        raw: raw.to_vec(),
        dfa: canon,
        anchor_start: astart,
        anchor_end: aend,
    })
}

fn longest_from(c: &Compiled, input: &[u8], start: usize) -> Option<usize> {
    if c.anchor_start && start != 0 {
        return None;
    }
    let mut state = c.dfa.start;
    let mut best: Option<usize> = None;
    if c.dfa.accept[state] {
        if !c.anchor_end || start == input.len() {
            best = Some(start);
        }
    }
    let mut pos = start;
    while pos < input.len() {
        let b = input[pos] as usize;
        match c.dfa.trans[state][b] {
            Some(t) => {
                state = t;
                pos += 1;
                if c.dfa.accept[state] {
                    if !c.anchor_end || pos == input.len() {
                        best = Some(pos);
                    }
                }
            }
            None => break,
        }
    }
    best
}

pub fn scan_one(c: &Compiled, input: &[u8]) -> Vec<(usize, usize)> {
    let mut spans = Vec::new();
    let mut start = 0usize;
    while start <= input.len() {
        match longest_from(c, input, start) {
            Some(end) => {
                spans.push((start, end));
                if end > start {
                    start = end;
                } else {
                    start += 1;
                }
            }
            None => {
                start += 1;
            }
        }
    }
    spans
}

fn json_escape(raw: &[u8]) -> String {
    let mut out = String::new();
    for &b in raw {
        match b {
            b'"' => out.push_str("\\\""),
            b'\\' => out.push_str("\\\\"),
            0x00..=0x1F => out.push_str(&format!("\\u{:04x}", b)),
            _ => out.push(b as char),
        }
    }
    out
}

pub fn render_report(items: &[(Vec<u8>, Vec<(usize, usize)>)]) -> String {
    let mut out = String::new();
    out.push_str("{\"patterns\": [");
    let mut first_entry = true;
    for (raw, spans) in items {
        if first_entry {
            first_entry = false;
        } else {
            out.push_str(", ");
        }
        out.push_str("{\"pattern\": \"");
        out.push_str(&json_escape(raw));
        out.push_str("\", \"matches\": [");
        let mut first_span = true;
        for (s, e) in spans {
            if first_span {
                first_span = false;
            } else {
                out.push_str(", ");
            }
            out.push_str(&format!("[{}, {}]", s, e));
        }
        out.push_str("]}");
    }
    out.push_str("]}");
    out.push('\n');
    out
}
RSXEOF
cd "$APP"
cargo build --release
