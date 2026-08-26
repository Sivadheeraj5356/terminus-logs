//! Policy string parsing: `v=sap1` then whitespace-separated terms. Frozen
//! evidence.

use crate::error::{ParseError, PResult};
use crate::mechanism::parse_mechanism;
use crate::term::{Mech, Term};

pub struct Policy {
    pub directives: Vec<Term>,
    pub redirect: Option<String>,
    pub has_all: bool,
}

pub fn parse_policy(text: &str) -> PResult<Policy> {
    let mut toks = text.split_whitespace();
    match toks.next() {
        Some("v=sap1") => {}
        _ => return Err(ParseError),
    }
    let mut directives = Vec::new();
    let mut redirect: Option<String> = None;
    let mut has_all = false;
    for tok in toks {
        if let Some(target) = tok.strip_prefix("redirect=") {
            if redirect.is_some() || target.is_empty() {
                return Err(ParseError);
            }
            redirect = Some(target.to_string());
            continue;
        }
        let (qual, body) = match tok.chars().next() {
            Some(c @ ('+' | '-' | '~' | '?')) => (c, &tok[1..]),
            _ => ('+', tok),
        };
        let mech = parse_mechanism(body)?;
        if matches!(mech, Mech::All) {
            has_all = true;
        }
        directives.push(Term {
            raw: tok.to_string(),
            qual,
            mech,
        });
    }
    Ok(Policy {
        directives,
        redirect,
        has_all,
    })
}
