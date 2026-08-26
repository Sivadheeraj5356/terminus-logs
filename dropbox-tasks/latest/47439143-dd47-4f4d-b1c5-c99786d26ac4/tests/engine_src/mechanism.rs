//! Mechanism parsing: turn a directive body (qualifier already stripped) into a
//! Mech, or reject it. Frozen evidence.

use crate::cidr::parse_cidr;
use crate::error::{ParseError, PResult};
use crate::term::Mech;

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
        Ok(Mech::Ip4(parse_cidr(c).ok_or(ParseError)?))
    } else if let Some(d) = body.strip_prefix("include:") {
        if d.is_empty() {
            return Err(ParseError);
        }
        Ok(Mech::Include(d.to_string()))
    } else {
        Err(ParseError)
    }
}
