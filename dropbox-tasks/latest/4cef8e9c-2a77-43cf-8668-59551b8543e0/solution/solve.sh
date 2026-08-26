#!/bin/bash
set -euo pipefail

app_dir="${MATCHBOOK_APP:-/app/matchbook}"
mkdir -p "$app_dir"

cat > "$app_dir/main.rs" <<'RUST'
use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::process;
use std::str;

#[derive(Clone)]
struct Case {
    id: String,
    trump: u8,
    broken: bool,
    leader: u8,
    maximize: u8,
    tricks: u8,
    table: Vec<u8>,
    hands: [u32; 4],
}

#[derive(Clone, Hash, Eq, PartialEq)]
struct State {
    hands: [u32; 4],
    leader: u8,
    table: Vec<u8>,
    broken: bool,
}

#[derive(Clone)]
struct ResultNode {
    value: u8,
    line: Vec<u8>,
}

fn suit(card: u8) -> u8 {
    card / 8
}

fn rank(card: u8) -> u8 {
    card % 8
}

fn pkey(card: u8) -> u8 {
    rank(card) * 4 + suit(card)
}

fn card_code(card: u8) -> String {
    let suits = [b'S', b'H', b'D', b'C'];
    let ranks = [b'7', b'8', b'9', b'T', b'J', b'Q', b'K', b'A'];
    String::from_utf8(vec![suits[suit(card) as usize], ranks[rank(card) as usize]]).unwrap()
}

fn parse_card(token: &str) -> Result<u8, String> {
    let bytes = token.as_bytes();
    if bytes.len() != 2 {
        return Err(format!("invalid card {token}"));
    }
    let s = match bytes[0] {
        b'S' => 0,
        b'H' => 1,
        b'D' => 2,
        b'C' => 3,
        _ => return Err(format!("invalid card {token}")),
    };
    let r = match bytes[1] {
        b'7' => 0,
        b'8' => 1,
        b'9' => 2,
        b'T' => 3,
        b'J' => 4,
        b'Q' => 5,
        b'K' => 6,
        b'A' => 7,
        _ => return Err(format!("invalid card {token}")),
    };
    Ok(s * 8 + r)
}

fn parse_u8(token: &str, low: u8, high: u8, name: &str) -> Result<u8, String> {
    if token.is_empty() || !token.bytes().all(|b| b.is_ascii_digit()) {
        return Err(format!("invalid {name}"));
    }
    let value: u16 = token.parse().map_err(|_| format!("invalid {name}"))?;
    if value < low as u16 || value > high as u16 {
        return Err(format!("invalid {name}"));
    }
    Ok(value as u8)
}

fn exact<'a>(tokens: &'a [&str], key: &str, count: usize) -> Result<&'a [&'a str], String> {
    if tokens.len() != count || tokens.first().copied() != Some(key) {
        return Err(format!("expected {key}"));
    }
    Ok(tokens)
}

fn card_list(tokens: &[&str], start: usize) -> Result<Vec<u8>, String> {
    tokens[start..].iter().map(|token| parse_card(token)).collect()
}

fn bit(card: u8) -> u32 {
    1u32 << card
}

fn contains(hand: u32, card: u8) -> bool {
    hand & bit(card) != 0
}

fn cards(hand: u32) -> Vec<u8> {
    let mut result: Vec<u8> = (0..32).filter(|card| contains(hand, *card)).collect();
    result.sort_by_key(|card| pkey(*card));
    result
}

fn legal(state: &State, trump: u8) -> Vec<u8> {
    let turn = ((state.leader as usize + state.table.len()) % 4) as usize;
    let hand = state.hands[turn];
    let all = cards(hand);
    if state.table.is_empty() {
        if !state.broken {
            let plain: Vec<u8> = all.iter().copied().filter(|card| suit(*card) != trump).collect();
            if !plain.is_empty() {
                return plain;
            }
        }
        return all;
    }
    let led = suit(state.table[0]);
    let following: Vec<u8> = all.iter().copied().filter(|card| suit(*card) == led).collect();
    if following.is_empty() { all } else { following }
}

fn winner(table: &[u8], trump: u8) -> usize {
    let led = suit(table[0]);
    let has_trump = table.iter().any(|card| suit(*card) == trump);
    let winning_suit = if has_trump { trump } else { led };
    table
        .iter()
        .enumerate()
        .filter(|(_, card)| suit(**card) == winning_suit)
        .max_by_key(|(_, card)| rank(**card))
        .map(|(index, _)| index)
        .unwrap()
}

fn advance(mut state: State, card: u8, trump: u8) -> (State, Option<u8>) {
    let turn = ((state.leader as usize + state.table.len()) % 4) as usize;
    state.hands[turn] &= !bit(card);
    state.table.push(card);
    if suit(card) == trump {
        state.broken = true;
    }
    if state.table.len() == 4 {
        let won = (state.leader as usize + winner(&state.table, trump)) % 4;
        state.leader = won as u8;
        state.table.clear();
        (state, Some(won as u8))
    } else {
        (state, None)
    }
}

fn validate_case(case: &Case) -> Result<State, String> {
    let mut seen = 0u32;
    for card in &case.table {
        if seen & bit(*card) != 0 {
            return Err(format!("case {} repeats a card", case.id));
        }
        seen |= bit(*card);
    }
    for hand in case.hands {
        if seen & hand != 0 {
            return Err(format!("case {} repeats a card", case.id));
        }
        seen |= hand;
    }

    for seat in 0..4usize {
        let offset = (seat + 4 - case.leader as usize) % 4;
        let played = offset < case.table.len();
        let expected = case.tricks as u32 - if played { 1 } else { 0 };
        if case.hands[seat].count_ones() != expected {
            return Err(format!("case {} has inconsistent hand sizes", case.id));
        }
    }

    let mut before = case.hands;
    for (index, card) in case.table.iter().enumerate() {
        let seat = (case.leader as usize + index) % 4;
        before[seat] |= bit(*card);
    }
    let mut state = State {
        hands: before,
        leader: case.leader,
        table: Vec::new(),
        broken: case.broken,
    };
    for card in &case.table {
        if !legal(&state, case.trump).contains(card) {
            return Err(format!("case {} has an illegal table", case.id));
        }
        let (next, completed) = advance(state, *card, case.trump);
        if completed.is_some() {
            return Err(format!("case {} has an invalid table", case.id));
        }
        state = next;
    }
    if state.hands != case.hands || state.table != case.table {
        return Err(format!("case {} has an invalid state", case.id));
    }
    Ok(state)
}

fn parse_file(text: &str) -> Result<Vec<Case>, String> {
    let lines: Vec<&str> = text
        .lines()
        .map(|line| line.trim_matches(|ch: char| ch.is_ascii_whitespace()))
        .filter(|line| !line.is_empty())
        .collect();
    if lines.first().copied() != Some("matchbook 1") {
        return Err("expected matchbook 1".to_string());
    }
    let mut index = 1usize;
    let mut result = Vec::new();
    let mut ids = HashSet::new();
    while index < lines.len() {
        if index + 11 >= lines.len() {
            return Err("incomplete case".to_string());
        }
        let parts: Vec<Vec<&str>> = lines[index..index + 12]
            .iter()
            .map(|line| line.split_ascii_whitespace().collect())
            .collect();

        exact(&parts[0], "case", 2)?;
        let id = parts[0][1];
        if id.is_empty()
            || id.len() > 32
            || !id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
            || !ids.insert(id.to_string())
        {
            return Err("invalid case identifier".to_string());
        }

        exact(&parts[1], "trump", 2)?;
        let trump = match parts[1][1] {
            "S" => 0,
            "H" => 1,
            "D" => 2,
            "C" => 3,
            _ => return Err(format!("case {id} has invalid trump")),
        };

        exact(&parts[2], "broken", 2)?;
        let broken = match parts[2][1] {
            "true" => true,
            "false" => false,
            _ => return Err(format!("case {id} has invalid broken state")),
        };

        exact(&parts[3], "leader", 2)?;
        let leader = parse_u8(parts[3][1], 0, 3, "leader")?;
        exact(&parts[4], "maximize", 2)?;
        let maximize = parse_u8(parts[4][1], 0, 1, "maximize")?;
        exact(&parts[5], "tricks", 2)?;
        let tricks = parse_u8(parts[5][1], 1, 5, "tricks")?;

        if parts[6].first().copied() != Some("table") || parts[6].len() > 4 {
            return Err(format!("case {id} has invalid table"));
        }
        let table = card_list(&parts[6], 1)?;

        let mut hands = [0u32; 4];
        for seat in 0..4usize {
            let row = &parts[7 + seat];
            if row.len() < 2 || row[0] != "hand" || row[1] != seat.to_string() {
                return Err(format!("case {id} has invalid hand order"));
            }
            for card in card_list(row, 2)? {
                if contains(hands[seat], card) {
                    return Err(format!("case {id} repeats a card"));
                }
                hands[seat] |= bit(card);
            }
        }
        exact(&parts[11], "end", 1)?;

        let case = Case {
            id: id.to_string(),
            trump,
            broken,
            leader,
            maximize,
            tricks,
            table,
            hands,
        };
        validate_case(&case)?;
        result.push(case);
        index += 12;
    }
    if result.is_empty() {
        return Err("at least one case is required".to_string());
    }
    Ok(result)
}

struct Solver {
    trump: u8,
    maximize: u8,
    memo: HashMap<State, ResultNode>,
}

impl Solver {
    fn branch(&mut self, state: &State, card: u8) -> ResultNode {
        let (next, won) = advance(state.clone(), card, self.trump);
        let child = self.evaluate(next);
        let gain = won.map_or(0, |seat| u8::from(seat % 2 == self.maximize));
        let mut line = Vec::with_capacity(child.line.len() + 1);
        line.push(card);
        line.extend(child.line);
        ResultNode { value: gain + child.value, line }
    }

    fn evaluate(&mut self, state: State) -> ResultNode {
        if let Some(result) = self.memo.get(&state) {
            return result.clone();
        }
        if state.hands.iter().all(|hand| *hand == 0) {
            return ResultNode { value: 0, line: Vec::new() };
        }
        let turn = ((state.leader as usize + state.table.len()) % 4) as u8;
        let maximizing_turn = turn % 2 == self.maximize;
        let mut best: Option<ResultNode> = None;
        for card in legal(&state, self.trump) {
            let candidate = self.branch(&state, card);
            let replace = match &best {
                None => true,
                Some(current) if maximizing_turn => candidate.value > current.value,
                Some(current) => candidate.value < current.value,
            };
            if replace {
                best = Some(candidate);
            }
        }
        let result = best.unwrap();
        self.memo.insert(state, result.clone());
        result
    }
}

fn solve_case(case: &Case) -> String {
    let state = validate_case(case).unwrap();
    let turn = ((state.leader as usize + state.table.len()) % 4) as u8;
    let root_cards = legal(&state, case.trump);
    let mut solver = Solver { trump: case.trump, maximize: case.maximize, memo: HashMap::new() };
    let mut moves = Vec::new();
    for card in root_cards {
        let result = solver.branch(&state, card);
        moves.push((card, result.value));
    }
    let result = solver.evaluate(state);

    let moves_json = moves
        .iter()
        .map(|(card, value)| format!("{{\"card\":\"{}\",\"value\":{value}}}", card_code(*card)))
        .collect::<Vec<String>>()
        .join(",");
    let line_json = result
        .line
        .iter()
        .map(|card| format!("\"{}\"", card_code(*card)))
        .collect::<Vec<String>>()
        .join(",");
    format!(
        "{{\"case\":\"{}\",\"turn\":{turn},\"moves\":[{moves_json}],\"best\":\"{}\",\"value\":{},\"line\":[{line_json}]}}",
        case.id,
        card_code(result.line[0]),
        result.value
    )
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 || args[1] != "solve" {
        return Err("usage: matchbook solve FILE".to_string());
    }
    let bytes = fs::read(&args[2]).map_err(|_| "cannot read input".to_string())?;
    let text = str::from_utf8(&bytes).map_err(|_| "input is not UTF-8".to_string())?;
    let cases = parse_file(text)?;
    let output: Vec<String> = cases.iter().map(solve_case).collect();
    println!("{}", output.join("\n"));
    Ok(())
}

fn main() {
    if let Err(message) = run() {
        eprintln!("error: {message}");
        process::exit(1);
    }
}
RUST

rustc --edition=2021 -O "$app_dir/main.rs" -o "$app_dir/matchbook"
chmod 0755 "$app_dir/matchbook"
