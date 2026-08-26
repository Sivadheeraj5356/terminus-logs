#!/bin/bash
set -euo pipefail
APP=/app
mkdir -p "$APP/src"
cat > "$APP/src/main.rs" <<'RSXEOF'
mod lexer;
mod ast;
mod parser;
mod nfa;
mod dfa;
mod minimize;
mod scan;
mod cli;

use std::process::exit;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    exit(cli::run(&args));
}
RSXEOF
cat > "$APP/src/ast.rs" <<'RSXEOF'
#[derive(Clone, Debug)]
pub enum Node {
    Empty,
    Byte(u8),
    Class(Vec<bool>),
    Concat(Vec<Node>),
    Alt(Vec<Node>),
    Star(Box<Node>),
    Plus(Box<Node>),
    Opt(Box<Node>),
    AnchorStart,
    AnchorEnd,
}
RSXEOF
cat > "$APP/src/lexer.rs" <<'RSXEOF'
pub struct Lexer<'a> {
    pub bytes: &'a [u8],
    pub pos: usize,
}

impl<'a> Lexer<'a> {
    pub fn new(bytes: &'a [u8]) -> Self {
        Lexer { bytes, pos: 0 }
    }

    pub fn peek(&self) -> Option<u8> {
        self.bytes.get(self.pos).copied()
    }

    pub fn peek_at(&self, off: usize) -> Option<u8> {
        self.bytes.get(self.pos + off).copied()
    }

    pub fn bump(&mut self) -> Option<u8> {
        let b = self.bytes.get(self.pos).copied();
        if b.is_some() {
            self.pos += 1;
        }
        b
    }

    pub fn eat(&mut self, b: u8) -> bool {
        if self.peek() == Some(b) {
            self.pos += 1;
            true
        } else {
            false
        }
    }

    pub fn eof(&self) -> bool {
        self.pos >= self.bytes.len()
    }
}

pub fn hex_val(b: u8) -> Option<u8> {
    match b {
        b'0'..=b'9' => Some(b - b'0'),
        b'a'..=b'f' => Some(b - b'a' + 10),
        b'A'..=b'F' => Some(b - b'A' + 10),
        _ => None,
    }
}
RSXEOF
cat > "$APP/src/parser.rs" <<'RSXEOF'
use crate::ast::Node;
use crate::lexer::{hex_val, Lexer};

pub fn parse(pattern: &[u8]) -> Result<Node, String> {
    let mut lx = Lexer::new(pattern);
    let node = parse_alt(&mut lx)?;
    if !lx.eof() {
        return Err(format!("unexpected byte at offset {}", lx.pos));
    }
    validate_anchor_positions(&node)?;
    Ok(node)
}

fn contains_anchor(node: &Node) -> bool {
    match node {
        Node::AnchorStart | Node::AnchorEnd => true,
        Node::Concat(items) | Node::Alt(items) => items.iter().any(contains_anchor),
        Node::Star(inner) | Node::Plus(inner) | Node::Opt(inner) => contains_anchor(inner),
        _ => false,
    }
}

fn validate_anchor_positions(node: &Node) -> Result<(), String> {
    match node {
        Node::AnchorStart | Node::AnchorEnd => Ok(()),
        Node::Concat(items) => {
            let last = items.len() - 1;
            for (i, it) in items.iter().enumerate() {
                match it {
                    Node::AnchorStart if i == 0 => {}
                    Node::AnchorEnd if i == last => {}
                    _ => {
                        if contains_anchor(it) {
                            return Err("anchor not at pattern boundary".to_string());
                        }
                    }
                }
            }
            Ok(())
        }
        other => {
            if contains_anchor(other) {
                Err("anchor not at pattern boundary".to_string())
            } else {
                Ok(())
            }
        }
    }
}

fn parse_alt(lx: &mut Lexer) -> Result<Node, String> {
    let mut branches = vec![parse_concat(lx)?];
    while lx.eat(b'|') {
        branches.push(parse_concat(lx)?);
    }
    if branches.len() == 1 {
        Ok(branches.pop().unwrap())
    } else {
        Ok(Node::Alt(branches))
    }
}

fn parse_concat(lx: &mut Lexer) -> Result<Node, String> {
    let mut items: Vec<Node> = Vec::new();
    loop {
        match lx.peek() {
            None => break,
            Some(b'|') | Some(b')') => break,
            _ => {}
        }
        let atom = parse_atom(lx)?;
        let rep = apply_repeats(lx, atom)?;
        items.push(rep);
    }
    if items.is_empty() {
        Ok(Node::Empty)
    } else if items.len() == 1 {
        Ok(items.pop().unwrap())
    } else {
        Ok(Node::Concat(items))
    }
}

fn apply_repeats(lx: &mut Lexer, mut node: Node) -> Result<Node, String> {
    loop {
        match lx.peek() {
            Some(b'*') => {
                lx.bump();
                node = Node::Star(Box::new(node));
            }
            Some(b'+') => {
                lx.bump();
                node = Node::Plus(Box::new(node));
            }
            Some(b'?') => {
                lx.bump();
                node = Node::Opt(Box::new(node));
            }
            Some(b'{') => {
                if let Some((m, n)) = try_parse_counted(lx)? {
                    node = expand_counted(node, m, n);
                } else {
                    break;
                }
            }
            _ => break,
        }
    }
    Ok(node)
}

fn try_parse_counted(lx: &mut Lexer) -> Result<Option<(usize, Option<usize>)>, String> {
    let save = lx.pos;
    lx.bump();
    let m = match read_number(lx) {
        Some(v) => v,
        None => {
            lx.pos = save;
            return Ok(None);
        }
    };
    if lx.eat(b'}') {
        if m > 1024 {
            return Err("count out of range".to_string());
        }
        return Ok(Some((m, Some(m))));
    }
    if lx.eat(b',') {
        if lx.eat(b'}') {
            if m > 1024 {
                return Err("count out of range".to_string());
            }
            return Ok(Some((m, None)));
        }
        let n = match read_number(lx) {
            Some(v) => v,
            None => {
                lx.pos = save;
                return Ok(None);
            }
        };
        if !lx.eat(b'}') {
            lx.pos = save;
            return Ok(None);
        }
        if m > n {
            return Err("counted repetition with m > n".to_string());
        }
        if n > 1024 {
            return Err("count out of range".to_string());
        }
        return Ok(Some((m, Some(n))));
    }
    lx.pos = save;
    Ok(None)
}

fn read_number(lx: &mut Lexer) -> Option<usize> {
    let start = lx.pos;
    let mut val: usize = 0;
    while let Some(b) = lx.peek() {
        if b.is_ascii_digit() {
            val = val.saturating_mul(10).saturating_add((b - b'0') as usize);
            lx.bump();
        } else {
            break;
        }
    }
    if lx.pos == start {
        None
    } else {
        Some(val)
    }
}

fn expand_counted(node: Node, m: usize, n: Option<usize>) -> Node {
    let mut items: Vec<Node> = Vec::new();
    for _ in 0..m {
        items.push(node.clone());
    }
    match n {
        None => {
            items.push(Node::Star(Box::new(node)));
        }
        Some(nn) => {
            let mut opt: Node = Node::Empty;
            let extra = nn - m;
            let mut built: Vec<Node> = Vec::new();
            for _ in 0..extra {
                built.push(node.clone());
            }
            for i in (0..extra).rev() {
                let mut inner: Vec<Node> = Vec::new();
                inner.push(built[i].clone());
                if !is_empty_node(&opt) {
                    inner.push(opt);
                }
                let concat = if inner.len() == 1 {
                    inner.pop().unwrap()
                } else {
                    Node::Concat(inner)
                };
                opt = Node::Opt(Box::new(concat));
            }
            if !is_empty_node(&opt) {
                items.push(opt);
            }
        }
    }
    if items.is_empty() {
        Node::Empty
    } else if items.len() == 1 {
        items.pop().unwrap()
    } else {
        Node::Concat(items)
    }
}

fn is_empty_node(n: &Node) -> bool {
    matches!(n, Node::Empty)
}

fn parse_atom(lx: &mut Lexer) -> Result<Node, String> {
    match lx.peek() {
        Some(b'(') => {
            lx.bump();
            let inner = parse_alt(lx)?;
            if !lx.eat(b')') {
                return Err("unclosed group".to_string());
            }
            Ok(inner)
        }
        Some(b'[') => parse_class(lx),
        Some(b'.') => {
            lx.bump();
            let mut set = vec![true; 256];
            set[0x0A] = false;
            Ok(Node::Class(set))
        }
        Some(b'^') => {
            lx.bump();
            Ok(Node::AnchorStart)
        }
        Some(b'$') => {
            lx.bump();
            Ok(Node::AnchorEnd)
        }
        Some(b'\\') => {
            let b = parse_escape(lx)?;
            Ok(Node::Byte(b))
        }
        Some(b'*') | Some(b'+') | Some(b'?') => {
            Err("repetition with no preceding atom".to_string())
        }
        Some(b')') | Some(b']') | Some(b'}') => {
            Err("unexpected closing metacharacter".to_string())
        }
        Some(b'|') => Err("empty alternation branch handled by caller".to_string()),
        Some(_) => {
            let b = lx.bump().unwrap();
            Ok(Node::Byte(b))
        }
        None => Err("unexpected end of pattern".to_string()),
    }
}

fn parse_escape(lx: &mut Lexer) -> Result<u8, String> {
    lx.bump();
    match lx.bump() {
        Some(b'n') => Ok(0x0A),
        Some(b't') => Ok(0x09),
        Some(b'r') => Ok(0x0D),
        Some(b'f') => Ok(0x0C),
        Some(b'v') => Ok(0x0B),
        Some(b'0') => Ok(0x00),
        Some(b'\\') => Ok(0x5C),
        Some(b'.') => Ok(b'.'),
        Some(b'^') => Ok(b'^'),
        Some(b'$') => Ok(b'$'),
        Some(b'*') => Ok(b'*'),
        Some(b'+') => Ok(b'+'),
        Some(b'?') => Ok(b'?'),
        Some(b'(') => Ok(b'('),
        Some(b')') => Ok(b')'),
        Some(b'[') => Ok(b'['),
        Some(b']') => Ok(b']'),
        Some(b'{') => Ok(b'{'),
        Some(b'}') => Ok(b'}'),
        Some(b'|') => Ok(b'|'),
        Some(b'x') => {
            let hi = lx.bump().ok_or_else(|| "bad hex escape".to_string())?;
            let lo = lx.bump().ok_or_else(|| "bad hex escape".to_string())?;
            let h = hex_val(hi).ok_or_else(|| "bad hex escape".to_string())?;
            let l = hex_val(lo).ok_or_else(|| "bad hex escape".to_string())?;
            Ok(h * 16 + l)
        }
        _ => Err("invalid escape".to_string()),
    }
}

fn parse_class_escape(lx: &mut Lexer) -> Result<u8, String> {
    lx.bump();
    match lx.bump() {
        Some(b'n') => Ok(0x0A),
        Some(b't') => Ok(0x09),
        Some(b'r') => Ok(0x0D),
        Some(b'f') => Ok(0x0C),
        Some(b'v') => Ok(0x0B),
        Some(b'0') => Ok(0x00),
        Some(b'\\') => Ok(0x5C),
        Some(b']') => Ok(b']'),
        Some(b'^') => Ok(b'^'),
        Some(b'-') => Ok(b'-'),
        Some(b'x') => {
            let hi = lx.bump().ok_or_else(|| "bad hex escape".to_string())?;
            let lo = lx.bump().ok_or_else(|| "bad hex escape".to_string())?;
            let h = hex_val(hi).ok_or_else(|| "bad hex escape".to_string())?;
            let l = hex_val(lo).ok_or_else(|| "bad hex escape".to_string())?;
            Ok(h * 16 + l)
        }
        _ => Err("invalid class escape".to_string()),
    }
}

fn parse_class(lx: &mut Lexer) -> Result<Node, String> {
    let set = parse_class_set(lx)?;
    Ok(Node::Class(set))
}

fn parse_class_set(lx: &mut Lexer) -> Result<Vec<bool>, String> {
    if !lx.eat(b'[') {
        return Err("class must start with [".to_string());
    }
    let negate = lx.eat(b'^');
    let mut set = vec![false; 256];
    let mut first = true;
    loop {
        match lx.peek() {
            None => return Err("unterminated class".to_string()),
            Some(b']') => {
                lx.bump();
                break;
            }
            Some(b'-') if lx.peek_at(1) == Some(b'-') && lx.peek_at(2) == Some(b'[') => {
                lx.bump();
                lx.bump();
                let sub = parse_class_set(lx)?;
                for i in 0..256 {
                    if sub[i] {
                        set[i] = false;
                    }
                }
                first = false;
                continue;
            }
            Some(b'&') if lx.peek_at(1) == Some(b'&') && lx.peek_at(2) == Some(b'[') => {
                lx.bump();
                lx.bump();
                let sub = parse_class_set(lx)?;
                for i in 0..256 {
                    if !sub[i] {
                        set[i] = false;
                    }
                }
                first = false;
                continue;
            }
            Some(b'[') if lx.peek_at(1) == Some(b':') => {
                let bytes = parse_named_set(lx)?;
                for b in bytes {
                    set[b as usize] = true;
                }
                first = false;
                continue;
            }
            _ => {}
        }
        let lo = class_atom(lx)?;
        let is_last_dash = lo == b'-' && lx.peek() == Some(b']');
        if lo == b'-' && (first || is_last_dash) {
            set[b'-' as usize] = true;
            first = false;
            continue;
        }
        if lx.peek() == Some(b'-')
            && lx.peek_at(1).is_some()
            && lx.peek_at(1) != Some(b']')
            && !(lx.peek_at(1) == Some(b'-') && lx.peek_at(2) == Some(b'['))
        {
            lx.bump();
            let hi = class_atom(lx)?;
            if lo > hi {
                return Err("range low > high".to_string());
            }
            for b in lo..=hi {
                set[b as usize] = true;
            }
        } else {
            set[lo as usize] = true;
        }
        first = false;
    }
    if negate {
        for i in 0..256 {
            set[i] = !set[i];
        }
    }
    Ok(set)
}

fn class_atom(lx: &mut Lexer) -> Result<u8, String> {
    match lx.peek() {
        Some(b'\\') => parse_class_escape(lx),
        Some(_) => Ok(lx.bump().unwrap()),
        None => Err("unterminated class".to_string()),
    }
}

fn parse_named_set(lx: &mut Lexer) -> Result<Vec<u8>, String> {
    lx.bump();
    lx.bump();
    let mut name = Vec::new();
    loop {
        match lx.peek() {
            Some(b':') if lx.peek_at(1) == Some(b']') => {
                lx.bump();
                lx.bump();
                break;
            }
            Some(b) if b.is_ascii_lowercase() => {
                name.push(b);
                lx.bump();
            }
            _ => return Err("bad named set".to_string()),
        }
    }
    let mut out = Vec::new();
    let push_range = |out: &mut Vec<u8>, lo: u8, hi: u8| {
        for b in lo..=hi {
            out.push(b);
        }
    };
    match name.as_slice() {
        b"digit" => push_range(&mut out, 0x30, 0x39),
        b"lower" => push_range(&mut out, 0x61, 0x7A),
        b"upper" => push_range(&mut out, 0x41, 0x5A),
        b"alpha" => {
            push_range(&mut out, 0x61, 0x7A);
            push_range(&mut out, 0x41, 0x5A);
        }
        b"alnum" => {
            push_range(&mut out, 0x61, 0x7A);
            push_range(&mut out, 0x41, 0x5A);
            push_range(&mut out, 0x30, 0x39);
        }
        b"space" => {
            out.extend_from_slice(&[0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20]);
        }
        b"hexdigit" => {
            push_range(&mut out, 0x30, 0x39);
            push_range(&mut out, 0x41, 0x46);
            push_range(&mut out, 0x61, 0x66);
        }
        b"punct" => {
            push_range(&mut out, 0x21, 0x2F);
            push_range(&mut out, 0x3A, 0x40);
            push_range(&mut out, 0x5B, 0x60);
            push_range(&mut out, 0x7B, 0x7E);
        }
        _ => return Err("unknown named set".to_string()),
    }
    Ok(out)
}

pub fn split_anchors(node: &Node) -> (bool, bool, Node) {
    let mut start = false;
    let mut end = false;
    let stripped = strip_anchors(node, &mut start, &mut end);
    (start, end, stripped)
}

fn strip_anchors(node: &Node, start: &mut bool, end: &mut bool) -> Node {
    match node {
        Node::AnchorStart => {
            *start = true;
            Node::Empty
        }
        Node::AnchorEnd => {
            *end = true;
            Node::Empty
        }
        Node::Concat(items) => {
            let mut out = Vec::new();
            for it in items {
                let s = strip_anchors(it, start, end);
                if !matches!(s, Node::Empty) {
                    out.push(s);
                }
            }
            if out.is_empty() {
                Node::Empty
            } else if out.len() == 1 {
                out.pop().unwrap()
            } else {
                Node::Concat(out)
            }
        }
        other => other.clone(),
    }
}
RSXEOF
cat > "$APP/src/nfa.rs" <<'RSXEOF'
use crate::ast::Node;

#[derive(Clone)]
pub struct State {
    pub eps: Vec<usize>,
    pub trans: Vec<(Vec<bool>, usize)>,
}

pub struct Nfa {
    pub states: Vec<State>,
    pub start: usize,
    pub accept: usize,
}

impl Nfa {
    fn new_state(&mut self) -> usize {
        self.states.push(State {
            eps: Vec::new(),
            trans: Vec::new(),
        });
        self.states.len() - 1
    }

    fn add_eps(&mut self, from: usize, to: usize) {
        self.states[from].eps.push(to);
    }

    fn add_trans(&mut self, from: usize, set: Vec<bool>, to: usize) {
        self.states[from].trans.push((set, to));
    }
}

pub fn build(node: &Node) -> Nfa {
    let mut nfa = Nfa {
        states: Vec::new(),
        start: 0,
        accept: 0,
    };
    let s = nfa.new_state();
    let (frag_start, frag_end) = build_frag(&mut nfa, node);
    nfa.add_eps(s, frag_start);
    nfa.start = s;
    nfa.accept = frag_end;
    nfa
}

fn build_frag(nfa: &mut Nfa, node: &Node) -> (usize, usize) {
    match node {
        Node::Empty => {
            let s = nfa.new_state();
            let e = nfa.new_state();
            nfa.add_eps(s, e);
            (s, e)
        }
        Node::Byte(b) => {
            let s = nfa.new_state();
            let e = nfa.new_state();
            let mut set = vec![false; 256];
            set[*b as usize] = true;
            nfa.add_trans(s, set, e);
            (s, e)
        }
        Node::Class(set) => {
            let s = nfa.new_state();
            let e = nfa.new_state();
            nfa.add_trans(s, set.clone(), e);
            (s, e)
        }
        Node::Concat(items) => {
            let s = nfa.new_state();
            let mut cur = s;
            for it in items {
                let (fs, fe) = build_frag(nfa, it);
                nfa.add_eps(cur, fs);
                cur = fe;
            }
            (s, cur)
        }
        Node::Alt(branches) => {
            let s = nfa.new_state();
            let e = nfa.new_state();
            for br in branches {
                let (fs, fe) = build_frag(nfa, br);
                nfa.add_eps(s, fs);
                nfa.add_eps(fe, e);
            }
            (s, e)
        }
        Node::Star(inner) => {
            let s = nfa.new_state();
            let e = nfa.new_state();
            let (fs, fe) = build_frag(nfa, inner);
            nfa.add_eps(s, fs);
            nfa.add_eps(s, e);
            nfa.add_eps(fe, fs);
            nfa.add_eps(fe, e);
            (s, e)
        }
        Node::Plus(inner) => {
            let s = nfa.new_state();
            let e = nfa.new_state();
            let (fs, fe) = build_frag(nfa, inner);
            nfa.add_eps(s, fs);
            nfa.add_eps(fe, fs);
            nfa.add_eps(fe, e);
            (s, e)
        }
        Node::Opt(inner) => {
            let s = nfa.new_state();
            let e = nfa.new_state();
            let (fs, fe) = build_frag(nfa, inner);
            nfa.add_eps(s, fs);
            nfa.add_eps(s, e);
            nfa.add_eps(fe, e);
            (s, e)
        }
        Node::AnchorStart | Node::AnchorEnd => {
            let s = nfa.new_state();
            let e = nfa.new_state();
            nfa.add_eps(s, e);
            (s, e)
        }
    }
}
RSXEOF
cat > "$APP/src/dfa.rs" <<'RSXEOF'
use crate::nfa::Nfa;
use std::collections::BTreeMap;
use std::collections::BTreeSet;

pub struct Dfa {
    pub num_states: usize,
    pub start: usize,
    pub accept: Vec<bool>,
    pub trans: Vec<[Option<usize>; 256]>,
}

fn eps_closure(nfa: &Nfa, set: &BTreeSet<usize>) -> BTreeSet<usize> {
    let mut stack: Vec<usize> = set.iter().copied().collect();
    let mut closure: BTreeSet<usize> = set.clone();
    while let Some(s) = stack.pop() {
        for &t in &nfa.states[s].eps {
            if closure.insert(t) {
                stack.push(t);
            }
        }
    }
    closure
}

pub fn subset_construct(nfa: &Nfa) -> Dfa {
    let mut start_set = BTreeSet::new();
    start_set.insert(nfa.start);
    let start_closure = eps_closure(nfa, &start_set);

    let mut id_of: BTreeMap<BTreeSet<usize>, usize> = BTreeMap::new();
    let mut sets: Vec<BTreeSet<usize>> = Vec::new();
    let mut trans: Vec<[Option<usize>; 256]> = Vec::new();

    id_of.insert(start_closure.clone(), 0);
    sets.push(start_closure);
    trans.push([None; 256]);

    let mut work: Vec<usize> = vec![0];
    while let Some(cur) = work.pop() {
        let cur_set = sets[cur].clone();
        let mut targets: [BTreeSet<usize>; 256] =
            std::array::from_fn(|_| BTreeSet::new());
        for &st in &cur_set {
            for (set, to) in &nfa.states[st].trans {
                for b in 0..256 {
                    if set[b] {
                        targets[b].insert(*to);
                    }
                }
            }
        }
        for b in 0..256 {
            if targets[b].is_empty() {
                continue;
            }
            let closure = eps_closure(nfa, &targets[b]);
            let id = match id_of.get(&closure) {
                Some(&id) => id,
                None => {
                    let id = sets.len();
                    id_of.insert(closure.clone(), id);
                    sets.push(closure);
                    trans.push([None; 256]);
                    work.push(id);
                    id
                }
            };
            trans[cur][b] = Some(id);
        }
    }

    let accept: Vec<bool> = sets
        .iter()
        .map(|s| s.contains(&nfa.accept))
        .collect();

    Dfa {
        num_states: sets.len(),
        start: 0,
        accept,
        trans,
    }
}

pub fn prune_and_canonicalize(dfa: &Dfa) -> Dfa {
    let n = dfa.num_states;
    if n == 0 {
        return Dfa {
            num_states: 1,
            start: 0,
            accept: vec![false],
            trans: vec![[None; 256]],
        };
    }
    let mut live = vec![false; n];
    let mut rev: Vec<Vec<usize>> = vec![Vec::new(); n];
    for s in 0..n {
        for b in 0..256 {
            if let Some(t) = dfa.trans[s][b] {
                rev[t].push(s);
            }
        }
    }
    let mut stack: Vec<usize> = Vec::new();
    for s in 0..n {
        if dfa.accept[s] {
            live[s] = true;
            stack.push(s);
        }
    }
    while let Some(s) = stack.pop() {
        for &p in &rev[s] {
            if !live[p] {
                live[p] = true;
                stack.push(p);
            }
        }
    }

    if !live[dfa.start] {
        return Dfa {
            num_states: 1,
            start: 0,
            accept: vec![false],
            trans: vec![[None; 256]],
        };
    }

    let mut new_id: Vec<Option<usize>> = vec![None; n];
    let mut order: Vec<usize> = Vec::new();
    new_id[dfa.start] = Some(0);
    order.push(dfa.start);
    let mut head = 0;
    while head < order.len() {
        let s = order[head];
        head += 1;
        let mut edges: Vec<(usize, usize)> = Vec::new();
        for b in 0..256 {
            if let Some(t) = dfa.trans[s][b] {
                if live[t] {
                    edges.push((b, t));
                }
            }
        }
        edges.sort();
        for (_, t) in edges {
            if new_id[t].is_none() {
                new_id[t] = Some(order.len());
                order.push(t);
            }
        }
    }

    let m = order.len();
    let mut accept = vec![false; m];
    let mut trans: Vec<[Option<usize>; 256]> = vec![[None; 256]; m];
    for (nid, &old) in order.iter().enumerate() {
        accept[nid] = dfa.accept[old];
        for b in 0..256 {
            if let Some(t) = dfa.trans[old][b] {
                if live[t] {
                    trans[nid][b] = new_id[t];
                }
            }
        }
    }

    Dfa {
        num_states: m,
        start: 0,
        accept,
        trans,
    }
}

pub fn render(dfa: &Dfa) -> String {
    let mut out = String::new();
    out.push_str(&format!("states {}\n", dfa.num_states));
    out.push_str("start 0\n");
    let mut accepts: Vec<usize> = (0..dfa.num_states).filter(|&s| dfa.accept[s]).collect();
    accepts.sort();
    if accepts.is_empty() {
        out.push_str("accept\n");
    } else {
        let parts: Vec<String> = accepts.iter().map(|s| s.to_string()).collect();
        out.push_str(&format!("accept {}\n", parts.join(" ")));
    }
    for s in 0..dfa.num_states {
        out.push_str(&format!("{}:", s));
        let mut ranges: Vec<(usize, usize, usize)> = Vec::new();
        let mut b = 0usize;
        while b < 256 {
            match dfa.trans[s][b] {
                Some(t) => {
                    let lo = b;
                    let mut hi = b;
                    while hi + 1 < 256 && dfa.trans[s][hi + 1] == Some(t) {
                        hi += 1;
                    }
                    ranges.push((lo, hi, t));
                    b = hi + 1;
                }
                None => {
                    b += 1;
                }
            }
        }
        let mut first = true;
        for (lo, hi, t) in ranges {
            if first {
                out.push(' ');
                first = false;
            } else {
                out.push(';');
            }
            if lo == hi {
                out.push_str(&format!("{:02x}=>{}", lo, t));
            } else {
                out.push_str(&format!("{:02x}-{:02x}=>{}", lo, hi, t));
            }
        }
        out.push('\n');
    }
    out
}
RSXEOF
cat > "$APP/src/minimize.rs" <<'RSXEOF'
use crate::dfa::Dfa;

pub fn minimize(dfa: &Dfa) -> Dfa {
    let n = dfa.num_states;
    let dead = n;
    let total = n + 1;

    let mut delta: Vec<[usize; 256]> = vec![[dead; 256]; total];
    for s in 0..n {
        for b in 0..256 {
            delta[s][b] = match dfa.trans[s][b] {
                Some(t) => t,
                None => dead,
            };
        }
    }

    let mut block_of: Vec<usize> = vec![0; total];
    for s in 0..total {
        let is_acc = s < n && dfa.accept[s];
        block_of[s] = if is_acc { 1 } else { 0 };
    }
    let mut num_blocks = 2;

    loop {
        let mut changed = false;
        let mut next_block_of = block_of.clone();
        let mut next_num = 0;
        let mut signature_map: std::collections::HashMap<(usize, Vec<usize>), usize> =
            std::collections::HashMap::new();
        for s in 0..total {
            let mut sig: Vec<usize> = Vec::with_capacity(256);
            for b in 0..256 {
                sig.push(block_of[delta[s][b]]);
            }
            let key = (block_of[s], sig);
            let id = match signature_map.get(&key) {
                Some(&id) => id,
                None => {
                    let id = next_num;
                    next_num += 1;
                    signature_map.insert(key, id);
                    id
                }
            };
            next_block_of[s] = id;
        }
        if next_num != num_blocks {
            changed = true;
        }
        block_of = next_block_of;
        num_blocks = next_num;
        if !changed {
            break;
        }
    }

    let dead_block = block_of[dead];

    let mut rep: Vec<Option<usize>> = vec![None; num_blocks];
    for s in 0..total {
        let b = block_of[s];
        if rep[b].is_none() {
            rep[b] = Some(s);
        }
    }

    let mut compact_id: Vec<Option<usize>> = vec![None; num_blocks];
    let mut count = 0;
    for b in 0..num_blocks {
        if b == dead_block {
            continue;
        }
        compact_id[b] = Some(count);
        count += 1;
    }

    let mut accept = vec![false; count];
    let mut trans: Vec<[Option<usize>; 256]> = vec![[None; 256]; count];
    for b in 0..num_blocks {
        if b == dead_block {
            continue;
        }
        let cid = compact_id[b].unwrap();
        let r = rep[b].unwrap();
        accept[cid] = r < n && dfa.accept[r];
        for sym in 0..256 {
            let tgt_block = block_of[delta[r][sym]];
            if tgt_block == dead_block {
                continue;
            }
            trans[cid][sym] = compact_id[tgt_block];
        }
    }

    let start_block = block_of[dfa.start];
    let start = compact_id[start_block].unwrap_or(0);

    Dfa {
        num_states: count,
        start,
        accept,
        trans,
    }
}
RSXEOF
cat > "$APP/src/cli.rs" <<'RSXEOF'
use crate::dfa::{self};
use crate::minimize;
use crate::nfa;
use crate::parser;
use std::io::Write;

pub fn run(args: &[String]) -> i32 {
    if args.len() < 2 {
        eprintln!("usage: rsx <compile|scan> ...");
        return 2;
    }
    match args[1].as_str() {
        "compile" => run_compile(&args[2..]),
        "scan" => 1,
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
RSXEOF
cat > "$APP/src/scan.rs" <<'RSXEOF'
use crate::dfa::Dfa;
use crate::parser;

pub struct Compiled {
    pub raw: Vec<u8>,
    pub dfa: Dfa,
    pub anchor_start: bool,
    pub anchor_end: bool,
}

pub fn compile_pattern(raw: &[u8]) -> Result<Compiled, String> {
    let _ = parser::parse(raw)?;
    Err("scan not implemented".to_string())
}

pub fn scan_one(_c: &Compiled, _input: &[u8]) -> Vec<(usize, usize)> {
    Vec::new()
}

pub fn render_report(_items: &[(Vec<u8>, Vec<(usize, usize)>)]) -> String {
    String::new()
}
RSXEOF
cd "$APP"
cargo build --release
