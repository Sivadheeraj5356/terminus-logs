//! Policy and address parsing. Provided by the scaffold.
//!
//! This is syntax only: it turns a policy string into `Policy`/`Term`/`Mech`
//! and rejects malformed policies. It makes no evaluation decision.

use crate::model::{Mech, Policy, Term};

#[derive(Debug, Clone, Copy)]
pub struct ParseError;

pub type PResult<T> = Result<T, ParseError>;

/// Parse a dotted-quad into a big-endian u32. Rejects leading zeros and
/// out-of-range octets.
pub fn parse_ip(s: &str) -> Option<u32> {
    let mut count = 0;
    let mut v: u32 = 0;
    for p in s.split('.') {
        count += 1;
        if count > 4 {
            return None;
        }
        if p.is_empty() || !p.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        if p.len() > 1 && p.as_bytes()[0] == b'0' {
            return None;
        }
        let n: u32 = p.parse().ok()?;
        if n > 255 {
            return None;
        }
        v = (v << 8) | n;
    }
    if count == 4 {
        Some(v)
    } else {
        None
    }
}

/// Split an `ip4` body into its network address and prefix length. A bare
/// address is /32. The prefix is a decimal in 0..=32 and may carry leading
/// zeros.
pub fn parse_cidr(s: &str) -> Option<(u32, u8)> {
    let (addr, prefix) = match s.split_once('/') {
        Some((a, p)) => {
            let pr: u8 = p.parse().ok()?;
            if pr > 32 {
                return None;
            }
            (a, pr)
        }
        None => (s, 32u8),
    };
    Some((parse_ip(addr)?, prefix))
}

pub fn parse_mechanism(body: &str) -> PResult<Mech> {
    if body == "all" {
        Ok(Mech::All)
    } else if body == "a" {
        Ok(Mech::A(None))
    } else if let Some(d) = body.strip_prefix("a:") {
        Ok(Mech::A(Some(d.to_string())))
    } else if body == "mx" {
        Ok(Mech::Mx(None))
    } else if let Some(d) = body.strip_prefix("mx:") {
        Ok(Mech::Mx(Some(d.to_string())))
    } else if let Some(c) = body.strip_prefix("ip4:") {
        let (net, prefix) = parse_cidr(c).ok_or(ParseError)?;
        Ok(Mech::Ip4 { net, prefix })
    } else if let Some(d) = body.strip_prefix("include:") {
        if d.is_empty() {
            return Err(ParseError);
        }
        Ok(Mech::Include(d.to_string()))
    } else {
        Err(ParseError)
    }
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
