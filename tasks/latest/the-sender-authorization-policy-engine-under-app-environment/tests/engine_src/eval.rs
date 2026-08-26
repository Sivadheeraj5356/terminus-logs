//! The Sender Authorization Policy evaluator. Frozen evidence.

use crate::budget::{Budget, MAX_DELEGATION};
use crate::ctx::Ctx;
use crate::include::include_matches;
use crate::policy::parse_policy;
use crate::resolve::{a_match, mx_match};
use crate::result::SapResult;
use crate::term::{qualifier_result, Mech};
use crate::zone::Zone;

/// Evaluate `current`'s policy under `ctx`. Returns the result and, when a
/// directive settled it, that directive's raw token.
pub fn evaluate(
    zone: &Zone,
    current: &str,
    ctx: &Ctx,
    budget: &mut Budget,
    depth: u32,
) -> (SapResult, Option<String>) {
    if depth > MAX_DELEGATION {
        return (SapResult::PermError, None);
    }
    let sap = match zone.get(current).and_then(|r| r.sap.as_ref()) {
        Some(s) => s,
        None => return (SapResult::None_, None),
    };
    let pol = match parse_policy(sap) {
        Ok(p) => p,
        Err(_) => return (SapResult::PermError, None),
    };

    let mut settled: Option<(SapResult, String)> = None;

    for t in &pol.directives {
        let matched = match &t.mech {
            Mech::All => true,
            Mech::Ip4(c) => c.contains(ctx.ip),
            Mech::A(arg) => {
                if budget.charge().is_err() {
                    return (SapResult::PermError, None);
                }
                a_match(zone, arg, ctx.request, ctx.ip)
            }
            Mech::Mx(arg) => {
                if budget.charge().is_err() {
                    return (SapResult::PermError, None);
                }
                mx_match(zone, arg, ctx.request, ctx.ip)
            }
            Mech::Include(d) => {
                if budget.charge().is_err() {
                    return (SapResult::PermError, None);
                }
                let (r, _) = evaluate(zone, d, ctx, budget, depth + 1);
                if r == SapResult::PermError {
                    return (SapResult::PermError, None);
                }
                include_matches(r)
            }
        };
        if matched {
            settled = Some((qualifier_result(t.qual), t.raw.clone()));
        }
    }

    if let Some((r, tok)) = settled {
        return (r, Some(tok));
    }

    if let Some(rd) = &pol.redirect {
        if !pol.has_all {
            let sub = ctx.delegate(rd);
            let (r, tok) = evaluate(zone, rd, &sub, budget, depth + 1);
            if r == SapResult::None_ {
                return (SapResult::PermError, None);
            }
            return (r, tok);
        }
    }
    (SapResult::Neutral, None)
}
