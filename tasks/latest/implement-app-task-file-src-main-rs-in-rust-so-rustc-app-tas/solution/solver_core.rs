use std::collections::{HashMap, HashSet};
use std::env;
use std::fmt::Write;
use std::fs;

#[derive(Clone)]
struct Key {
    issuer: String,
    subject: String,
    not_before: i64,
    not_after: i64,
    trusted: bool,
}

#[derive(Clone)]
struct Image {
    name: String,
    digest: String,
    env: String,
    tier: String,
}

#[derive(Clone)]
struct Attest {
    name: String,
    digest: String,
    predicate: String,
    builder: String,
    key: String,
    timestamp: i64,
    log_index: i64,
    source_digest: String,
    order: usize,
}

#[derive(Clone)]
struct LogRoot {
    log_id: String,
    root_hash: String,
    not_before: i64,
    not_after: i64,
    trusted: bool,
}

#[derive(Clone)]
struct Bundle {
    log_index: i64,
    log_id: String,
    integrated_time: i64,
    tree_size: i64,
    root_hash: String,
}

#[derive(Clone)]
struct Checkpoint {
    log_id: String,
    tree_size: i64,
    root_hash: String,
    prev_root_hash: String,
    prev_tree_size: i64,
    trusted: bool,
}

#[derive(Clone)]
struct Witness {
    log_id: String,
    tree_size: i64,
    root_hash: String,
    key: String,
    timestamp: i64,
    source_digest: String,
    trusted: bool,
}

#[derive(Clone)]
struct WitnessReq {
    log_id: String,
    root_prefix: String,
    min_count: usize,
    distinct: bool,
    max_age: i64,
    source_prefix: String,
}

#[derive(Clone)]
struct RootPin {
    env: String,
    tier: String,
    log_id: String,
    root_prefix: String,
    not_before: i64,
    not_after: i64,
    trusted: bool,
}

#[derive(Clone)]
struct SplitView {
    log_id: String,
    tree_size: i64,
    root_hash: String,
    trusted: bool,
}

#[derive(Clone)]
struct Bind {
    builder: String,
    issuer: String,
    subject_prefix: String,
    source_prefix: String,
    env: String,
    tier: String,
    not_before: i64,
    not_after: i64,
    trusted: bool,
}

#[derive(Clone)]
struct Embargo {
    env: String,
    tier: String,
    builder: String,
    source_prefix: String,
    start: i64,
    end: i64,
}

#[derive(Clone)]
struct KeyScope {
    key: String,
    env: String,
    tier: String,
    builder: String,
    source_prefix: String,
    not_before: i64,
    not_after: i64,
    trusted: bool,
}

#[derive(Clone)]
struct Chain {
    env: String,
    tier: String,
    predicate: String,
    builder: String,
    prev_predicate: String,
    prev_builder: String,
    max_delta: i64,
    source_prefix: String,
}

#[derive(Clone)]
struct Hold {
    env: String,
    tier: String,
    builder: String,
    source_prefix: String,
    marker_predicate: String,
    marker_builder: String,
    marker_issuer: String,
    marker_source_prefix: String,
    start: i64,
    end: i64,
}

#[derive(Clone)]
struct Requirement {
    predicate: String,
    builder: String,
    issuer: String,
    max_age: i64,
    min_log: i64,
    source_prefix: String,
    subject_prefix: String,
}

#[derive(Clone)]
enum Policy {
    Require {
        env: String,
        tier: String,
        req: Requirement,
        hard: bool,
    },
    Quorum {
        env: String,
        tier: String,
        label: String,
        min_count: usize,
        distinct: bool,
        min_source_groups: usize,
        hard: bool,
    },
}

#[derive(Clone)]
struct Evidence {
    request: String,
    predicate: String,
    builder: String,
    key: String,
    timestamp: i64,
    log_index: i64,
    source_digest: String,
}

#[derive(Clone)]
struct Delegate {
    parent: String,
    child: String,
    not_before: i64,
    not_after: i64,
    subject_prefix: String,
    source_prefix: String,
}

fn js(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c <= '\u{1f}' => {
                write!(&mut out, "\\u{:04x}", c as u32).unwrap();
            }
            _ => out.push(c),
        }
    }
    out.push('"');
    out
}

fn is_revoked(key: &str, timestamp: i64, revokes: &[(String, Option<i64>, Option<i64>)]) -> bool {
    revokes.iter().any(|(rkey, start, end)| {
        rkey == key && match (start, end) {
            (Some(s), Some(e)) => *s <= timestamp && timestamp <= *e,
            _ => true,
        }
    })
}

fn is_compromised(key: &str, timestamp: i64, source_digest: &str, compromises: &[(String, i64, i64, String)]) -> bool {
    compromises.iter().any(|(ckey, start, end, prefix)| {
        ckey == key && *start <= timestamp && timestamp <= *end && (prefix == "*" || source_digest.starts_with(prefix))
    })
}

fn wildcard_match(rule_value: &str, actual: &str, prefix: bool) -> bool {
    rule_value == "*" || if prefix { actual.starts_with(rule_value) } else { rule_value == actual }
}

fn bind_ok(a: &Attest, key: &Key, env: &str, tier: &str, binds: &[Bind]) -> bool {
    let mut saw_builder = false;
    for b in binds.iter().filter(|b| b.builder == a.builder) {
        saw_builder = true;
        if b.trusted
            && b.not_before <= a.timestamp
            && a.timestamp <= b.not_after
            && wildcard_match(&b.issuer, &key.issuer, false)
            && wildcard_match(&b.subject_prefix, &key.subject, true)
            && wildcard_match(&b.source_prefix, &a.source_digest, true)
            && wildcard_match(&b.env, env, false)
            && wildcard_match(&b.tier, tier, false)
        {
            return true;
        }
    }
    !saw_builder
}

fn embargoed(a: &Attest, now: i64, env: &str, tier: &str, embargoes: &[Embargo]) -> bool {
    embargoes.iter().any(|e| {
        wildcard_match(&e.env, env, false)
            && wildcard_match(&e.tier, tier, false)
            && wildcard_match(&e.builder, &a.builder, false)
            && wildcard_match(&e.source_prefix, &a.source_digest, true)
            && ((e.start <= now && now <= e.end) || (e.start <= a.timestamp && a.timestamp <= e.end))
    })
}

fn key_scope_ok(a: &Attest, env: &str, tier: &str, key_scopes: &[KeyScope]) -> bool {
    let mut saw_key = false;
    for scope in key_scopes.iter().filter(|scope| scope.key == a.key) {
        saw_key = true;
        if scope.trusted
            && scope.not_before <= a.timestamp
            && a.timestamp <= scope.not_after
            && wildcard_match(&scope.env, env, false)
            && wildcard_match(&scope.tier, tier, false)
            && wildcard_match(&scope.builder, &a.builder, false)
            && wildcard_match(&scope.source_prefix, &a.source_digest, true)
        {
            return true;
        }
    }
    !saw_key
}

fn valid(
    a: &Attest,
    r: &Requirement,
    now: i64,
    env: &str,
    tier: &str,
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
    roots: &[LogRoot],
    bundles: &[Bundle],
    checkpoints: &[Checkpoint],
    splitviews: &[SplitView],
    witnesses: &[Witness],
    witness_reqs: &[WitnessReq],
    root_pins: &[RootPin],
    binds: &[Bind],
    embargoes: &[Embargo],
    key_scopes: &[KeyScope],
    holds: &[Hold],
    chains: &[Chain],
    attest: &[Attest],
) -> bool {
    base_valid(a, r, now, env, tier, keys, revokes, compromises, delegates, roots, bundles, checkpoints, splitviews, witnesses, witness_reqs, root_pins, binds, embargoes, key_scopes, holds, attest)
        && chain_ok(a, now, env, tier, keys, revokes, compromises, delegates, roots, bundles, checkpoints, splitviews, witnesses, witness_reqs, root_pins, binds, embargoes, key_scopes, holds, chains, attest)
}

fn base_valid(
    a: &Attest,
    r: &Requirement,
    now: i64,
    env: &str,
    tier: &str,
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
    roots: &[LogRoot],
    bundles: &[Bundle],
    checkpoints: &[Checkpoint],
    splitviews: &[SplitView],
    witnesses: &[Witness],
    witness_reqs: &[WitnessReq],
    root_pins: &[RootPin],
    binds: &[Bind],
    embargoes: &[Embargo],
    key_scopes: &[KeyScope],
    holds: &[Hold],
    attest: &[Attest],
) -> bool {
    if a.predicate != r.predicate
        || a.builder != r.builder
        || a.log_index < r.min_log
        || now - a.timestamp > r.max_age
        || (r.source_prefix != "*" && !a.source_digest.starts_with(&r.source_prefix))
    {
        return false;
    }
    if embargoed(a, now, env, tier, embargoes) {
        return false;
    }
    if held(a, now, env, tier, holds, attest, keys, revokes, compromises, delegates, roots, bundles, checkpoints, splitviews, witnesses, witness_reqs, root_pins, binds, key_scopes) {
        return false;
    }
    if !transparent(a, env, tier, roots, bundles, checkpoints, splitviews, witnesses, witness_reqs, root_pins, keys, revokes, compromises, delegates) {
        return false;
    }
    if let Some(k) = keys.get(&a.key) {
        !is_revoked(&a.key, a.timestamp, revokes)
            && !is_compromised(&a.key, a.timestamp, &a.source_digest, compromises)
            && k.issuer == r.issuer
            && (r.subject_prefix == "*" || k.subject.starts_with(&r.subject_prefix))
            && k.not_before <= a.timestamp
            && a.timestamp <= k.not_after
            && bind_ok(a, k, env, tier, binds)
            && key_scope_ok(a, env, tier, key_scopes)
            && trusted_for(&a.key, a.timestamp, &a.source_digest, keys, revokes, compromises, delegates, &mut HashSet::new())
    } else {
        false
    }
}

fn chain_ok(
    a: &Attest,
    now: i64,
    env: &str,
    tier: &str,
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
    roots: &[LogRoot],
    bundles: &[Bundle],
    checkpoints: &[Checkpoint],
    splitviews: &[SplitView],
    witnesses: &[Witness],
    witness_reqs: &[WitnessReq],
    root_pins: &[RootPin],
    binds: &[Bind],
    embargoes: &[Embargo],
    key_scopes: &[KeyScope],
    holds: &[Hold],
    chains: &[Chain],
    attest: &[Attest],
) -> bool {
    let issuer = keys.get(&a.key).map(|k| k.issuer.as_str()).unwrap_or("");
    for c in chains {
        if !wildcard_match(&c.env, env, false)
            || !wildcard_match(&c.tier, tier, false)
            || c.predicate != a.predicate
            || c.builder != a.builder
            || !wildcard_match(&c.source_prefix, &a.source_digest, true)
        {
            continue;
        }
        let req = Requirement {
            predicate: c.prev_predicate.clone(),
            builder: c.prev_builder.clone(),
            issuer: issuer.to_string(),
            max_age: i64::MAX / 4,
            min_log: i64::MIN / 4,
            source_prefix: "*".to_string(),
            subject_prefix: "*".to_string(),
        };
        let found = attest.iter().any(|prev| {
            prev.name == a.name
                && prev.digest == a.digest
                && prev.timestamp <= a.timestamp
                && a.timestamp - prev.timestamp <= c.max_delta
                && prev.log_index < a.log_index
                && base_valid(prev, &req, now, env, tier, keys, revokes, compromises, delegates, roots, bundles, checkpoints, splitviews, witnesses, witness_reqs, root_pins, binds, embargoes, key_scopes, holds, attest)
        });
        if !found {
            return false;
        }
    }
    true
}

fn marker_valid(
    marker: &Attest,
    issuer: &str,
    source_prefix: &str,
    env: &str,
    tier: &str,
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
    roots: &[LogRoot],
    bundles: &[Bundle],
    checkpoints: &[Checkpoint],
    splitviews: &[SplitView],
    witnesses: &[Witness],
    witness_reqs: &[WitnessReq],
    root_pins: &[RootPin],
    binds: &[Bind],
    key_scopes: &[KeyScope],
) -> bool {
    if source_prefix != "*" && !marker.source_digest.starts_with(source_prefix) {
        return false;
    }
    if !transparent(marker, env, tier, roots, bundles, checkpoints, splitviews, witnesses, witness_reqs, root_pins, keys, revokes, compromises, delegates) {
        return false;
    }
    if let Some(k) = keys.get(&marker.key) {
        k.issuer == issuer
            && !is_revoked(&marker.key, marker.timestamp, revokes)
            && !is_compromised(&marker.key, marker.timestamp, &marker.source_digest, compromises)
            && k.not_before <= marker.timestamp
            && marker.timestamp <= k.not_after
            && bind_ok(marker, k, env, tier, binds)
            && key_scope_ok(marker, env, tier, key_scopes)
            && trusted_for(&marker.key, marker.timestamp, &marker.source_digest, keys, revokes, compromises, delegates, &mut HashSet::new())
    } else {
        false
    }
}

fn held(
    a: &Attest,
    now: i64,
    env: &str,
    tier: &str,
    holds: &[Hold],
    attest: &[Attest],
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
    roots: &[LogRoot],
    bundles: &[Bundle],
    checkpoints: &[Checkpoint],
    splitviews: &[SplitView],
    witnesses: &[Witness],
    witness_reqs: &[WitnessReq],
    root_pins: &[RootPin],
    binds: &[Bind],
    key_scopes: &[KeyScope],
) -> bool {
    for h in holds {
        if !wildcard_match(&h.env, env, false)
            || !wildcard_match(&h.tier, tier, false)
            || !wildcard_match(&h.builder, &a.builder, false)
            || !wildcard_match(&h.source_prefix, &a.source_digest, true)
            || !((h.start <= now && now <= h.end) || (h.start <= a.timestamp && a.timestamp <= h.end))
        {
            continue;
        }
        for marker in attest {
            if marker.name == a.name
                && marker.digest == a.digest
                && marker.predicate == h.marker_predicate
                && marker.builder == h.marker_builder
                && marker_valid(marker, &h.marker_issuer, &h.marker_source_prefix, env, tier, keys, revokes, compromises, delegates, roots, bundles, checkpoints, splitviews, witnesses, witness_reqs, root_pins, binds, key_scopes)
            {
                return true;
            }
        }
    }
    false
}

fn transparent(
    a: &Attest,
    env: &str,
    tier: &str,
    roots: &[LogRoot],
    bundles: &[Bundle],
    checkpoints: &[Checkpoint],
    splitviews: &[SplitView],
    witnesses: &[Witness],
    witness_reqs: &[WitnessReq],
    root_pins: &[RootPin],
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
) -> bool {
    let mut saw_bundle = false;
    for b in bundles.iter().filter(|b| b.log_index == a.log_index) {
        saw_bundle = true;
        if b.integrated_time != a.timestamp || b.tree_size <= a.log_index {
            continue;
        }
        if splitviews.iter().any(|s| {
            s.log_id == b.log_id && s.tree_size == b.tree_size && s.root_hash == b.root_hash && s.trusted
        }) {
            continue;
        }
        let root_ok = roots.iter().any(|r| {
            r.log_id == b.log_id
                && r.root_hash == b.root_hash
                && r.trusted
                && r.not_before <= b.integrated_time
                && b.integrated_time <= r.not_after
                && checkpoint_ok(b, roots, checkpoints)
        });
        if root_ok && root_pin_ok(b, env, tier, root_pins) && witness_ok(b, witnesses, witness_reqs, keys, revokes, compromises, delegates) {
            return true;
        }
    }
    !saw_bundle
}

fn checkpoint_ok(bundle: &Bundle, roots: &[LogRoot], checkpoints: &[Checkpoint]) -> bool {
    let matching: Vec<&Checkpoint> = checkpoints
        .iter()
        .filter(|c| c.log_id == bundle.log_id && c.tree_size == bundle.tree_size && c.root_hash == bundle.root_hash)
        .collect();
    if matching.is_empty() {
        return true;
    }
    matching.iter().any(|c| {
        c.trusted
            && c.prev_tree_size < bundle.tree_size
            && (c.prev_tree_size == 0
                || roots.iter().any(|r| {
                    r.log_id == bundle.log_id
                        && r.root_hash == c.prev_root_hash
                        && r.trusted
                        && r.not_after <= bundle.integrated_time
                }))
    })
}

fn root_pin_ok(bundle: &Bundle, env: &str, tier: &str, root_pins: &[RootPin]) -> bool {
    let mut saw = false;
    for pin in root_pins.iter().filter(|pin| {
        wildcard_match(&pin.env, env, false)
            && wildcard_match(&pin.tier, tier, false)
            && wildcard_match(&pin.log_id, &bundle.log_id, false)
    }) {
        saw = true;
        if pin.trusted
            && pin.not_before <= bundle.integrated_time
            && bundle.integrated_time <= pin.not_after
            && wildcard_match(&pin.root_prefix, &bundle.root_hash, true)
        {
            return true;
        }
    }
    !saw
}

fn witness_ok(
    bundle: &Bundle,
    witnesses: &[Witness],
    witness_reqs: &[WitnessReq],
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
) -> bool {
    let matching: Vec<&WitnessReq> = witness_reqs
        .iter()
        .filter(|r| r.log_id == bundle.log_id && (r.root_prefix == "*" || bundle.root_hash.starts_with(&r.root_prefix)))
        .collect();
    if matching.is_empty() {
        return true;
    }
    for req in matching {
        let mut chosen_keys: HashSet<String> = HashSet::new();
        let mut count = 0usize;
        for w in witnesses.iter().filter(|w| {
            w.log_id == bundle.log_id
                && w.tree_size == bundle.tree_size
                && w.root_hash == bundle.root_hash
                && w.trusted
                && w.timestamp <= bundle.integrated_time
                && bundle.integrated_time - w.timestamp <= req.max_age
                && (req.source_prefix == "*" || w.source_digest.starts_with(&req.source_prefix))
        }) {
            if req.distinct && chosen_keys.contains(&w.key) {
                continue;
            }
            let Some(k) = keys.get(&w.key) else {
                continue;
            };
            if w.timestamp < k.not_before
                || w.timestamp > k.not_after
                || is_revoked(&w.key, w.timestamp, revokes)
                || is_compromised(&w.key, w.timestamp, &w.source_digest, compromises)
                || !trusted_for(&w.key, w.timestamp, &w.source_digest, keys, revokes, compromises, delegates, &mut HashSet::new())
            {
                continue;
            }
            if req.distinct {
                chosen_keys.insert(w.key.clone());
            }
            count += 1;
            if count >= req.min_count {
                break;
            }
        }
        if count < req.min_count {
            return false;
        }
    }
    true
}

fn trusted_for(
    key: &str,
    timestamp: i64,
    source_digest: &str,
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
    seen: &mut HashSet<String>,
) -> bool {
    if seen.contains(key) {
        return false;
    }
    let Some(k) = keys.get(key) else {
        return false;
    };
    if is_revoked(key, timestamp, revokes)
        || is_compromised(key, timestamp, source_digest, compromises)
        || timestamp < k.not_before
        || timestamp > k.not_after
    {
        return false;
    }
    if k.trusted {
        return true;
    }
    seen.insert(key.to_string());
    for d in delegates {
        if d.child != key || timestamp < d.not_before || timestamp > d.not_after {
            continue;
        }
        if d.source_prefix != "*" && !source_digest.starts_with(&d.source_prefix) {
            continue;
        }
        if d.subject_prefix != "*" && !k.subject.starts_with(&d.subject_prefix) {
            continue;
        }
        if trusted_for(&d.parent, timestamp, source_digest, keys, revokes, compromises, delegates, seen) {
            seen.remove(key);
            return true;
        }
    }
    seen.remove(key);
    false
}

fn better(a: &Attest, b: &Attest) -> bool {
    a.timestamp > b.timestamp
        || (a.timestamp == b.timestamp
            && (a.log_index > b.log_index || (a.log_index == b.log_index && a.order < b.order)))
}

fn best_attestation<'a>(
    name: &str,
    digest: &str,
    req: &Requirement,
    now: i64,
    env: &str,
    tier: &str,
    attest: &'a [Attest],
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
    roots: &[LogRoot],
    bundles: &[Bundle],
    checkpoints: &[Checkpoint],
    splitviews: &[SplitView],
    witnesses: &[Witness],
    witness_reqs: &[WitnessReq],
    root_pins: &[RootPin],
    binds: &[Bind],
    embargoes: &[Embargo],
    key_scopes: &[KeyScope],
    holds: &[Hold],
    chains: &[Chain],
    used_orders: Option<&HashSet<usize>>,
) -> Option<&'a Attest> {
    let mut best: Option<&Attest> = None;
    for a in attest.iter().filter(|a| a.name == name && a.digest == digest) {
        if used_orders.map_or(false, |used| used.contains(&a.order)) {
            continue;
        }
        if valid(a, req, now, env, tier, keys, revokes, compromises, delegates, roots, bundles, checkpoints, splitviews, witnesses, witness_reqs, root_pins, binds, embargoes, key_scopes, holds, chains, attest) && best.map_or(true, |b| better(a, b)) {
            best = Some(a);
        }
    }
    best
}

fn source_group(source_digest: &str) -> &str {
    source_digest.split_once('/').map_or(source_digest, |(head, _)| head)
}

fn score(selected: &[Option<Attest>]) -> Vec<i64> {
    let mut out = vec![selected.iter().filter(|x| x.is_some()).count() as i64];
    let groups: HashSet<&str> = selected
        .iter()
        .filter_map(|x| x.as_ref().map(|a| source_group(&a.source_digest)))
        .collect();
    out.push(groups.len() as i64);
    for item in selected {
        if let Some(a) = item {
            out.extend([1, a.timestamp, a.log_index, -(a.order as i64)]);
        } else {
            out.extend([0, 0, 0, 0]);
        }
    }
    out
}

fn select_quorum(
    name: &str,
    digest: &str,
    label: &str,
    min_count: usize,
    distinct: bool,
    min_source_groups: usize,
    now: i64,
    env: &str,
    tier: &str,
    members: &HashMap<String, Vec<Requirement>>,
    attest: &[Attest],
    keys: &HashMap<String, Key>,
    revokes: &[(String, Option<i64>, Option<i64>)],
    compromises: &[(String, i64, i64, String)],
    delegates: &[Delegate],
    roots: &[LogRoot],
    bundles: &[Bundle],
    checkpoints: &[Checkpoint],
    splitviews: &[SplitView],
    witnesses: &[Witness],
    witness_reqs: &[WitnessReq],
    root_pins: &[RootPin],
    binds: &[Bind],
    embargoes: &[Embargo],
    key_scopes: &[KeyScope],
    holds: &[Hold],
    chains: &[Chain],
    used_orders: Option<&HashSet<usize>>,
) -> Option<Vec<(Requirement, Attest)>> {
    let group = members.get(label).cloned().unwrap_or_default();
    let mut lists: Vec<Vec<Attest>> = Vec::new();
    for member in &group {
        let mut cands: Vec<Attest> = attest
            .iter()
            .filter(|a| {
                a.name == name
                    && a.digest == digest
                    && !used_orders.map_or(false, |used| used.contains(&a.order))
                    && valid(a, member, now, env, tier, keys, revokes, compromises, delegates, roots, bundles, checkpoints, splitviews, witnesses, witness_reqs, root_pins, binds, embargoes, key_scopes, holds, chains, attest)
            })
            .cloned()
            .collect();
        cands.sort_by(|a, b| {
            b.timestamp
                .cmp(&a.timestamp)
                .then(b.log_index.cmp(&a.log_index))
                .then(a.order.cmp(&b.order))
        });
        lists.push(cands);
    }

    struct Search<'a> {
        lists: &'a [Vec<Attest>],
        min_count: usize,
        distinct: bool,
        min_source_groups: usize,
        unique: bool,
        best: Option<Vec<Option<Attest>>>,
        best_score: Vec<i64>,
    }

    impl<'a> Search<'a> {
        fn dfs(
            &mut self,
            idx: usize,
            used_keys: &mut HashSet<String>,
            used_records: &mut HashSet<usize>,
            selected: &mut Vec<Option<Attest>>,
        ) {
            if idx == self.lists.len() {
                if selected.iter().filter(|x| x.is_some()).count() < self.min_count {
                    return;
                }
                let groups: HashSet<&str> = selected
                    .iter()
                    .filter_map(|x| x.as_ref().map(|a| source_group(&a.source_digest)))
                    .collect();
                if groups.len() < self.min_source_groups {
                    return;
                }
                let sc = score(selected);
                if self.best.is_none() || sc > self.best_score {
                    self.best_score = sc;
                    self.best = Some(selected.clone());
                }
                return;
            }
            selected.push(None);
            self.dfs(idx + 1, used_keys, used_records, selected);
            selected.pop();
            for cand in &self.lists[idx] {
                if self.distinct && used_keys.contains(&cand.key) {
                    continue;
                }
                if self.unique && used_records.contains(&cand.order) {
                    continue;
                }
                selected.push(Some(cand.clone()));
                if self.distinct {
                    used_keys.insert(cand.key.clone());
                }
                if self.unique {
                    used_records.insert(cand.order);
                }
                self.dfs(idx + 1, used_keys, used_records, selected);
                if self.unique {
                    used_records.remove(&cand.order);
                }
                if self.distinct {
                    used_keys.remove(&cand.key);
                }
                selected.pop();
            }
        }
    }

    let mut search = Search {
        lists: &lists,
        min_count,
        distinct,
        min_source_groups,
        unique: used_orders.is_some(),
        best: None,
        best_score: Vec::new(),
    };
    let mut used_records = used_orders.cloned().unwrap_or_default();
    search.dfs(0, &mut HashSet::new(), &mut used_records, &mut Vec::new());
    search.best.map(|chosen| {
        group
            .into_iter()
            .zip(chosen)
            .filter_map(|(member, att)| att.map(|a| (member, a)))
            .collect()
    })
}

fn solve(input: &str) -> String {
    let mut keys = HashMap::new();
    let mut images: Vec<Image> = Vec::new();
    let mut attest: Vec<Attest> = Vec::new();
    let mut policies: Vec<Policy> = Vec::new();
    let mut members: HashMap<String, Vec<Requirement>> = HashMap::new();
    let mut delegates: Vec<Delegate> = Vec::new();
    let mut requests: Vec<(String, String, i64)> = Vec::new();
    let mut revokes: Vec<(String, Option<i64>, Option<i64>)> = Vec::new();
    let mut roots: Vec<LogRoot> = Vec::new();
    let mut bundles: Vec<Bundle> = Vec::new();
    let mut checkpoints: Vec<Checkpoint> = Vec::new();
    let mut witnesses: Vec<Witness> = Vec::new();
    let mut witness_reqs: Vec<WitnessReq> = Vec::new();
    let mut root_pins: Vec<RootPin> = Vec::new();
    let mut compromises: Vec<(String, i64, i64, String)> = Vec::new();
    let mut splitviews: Vec<SplitView> = Vec::new();
    let mut binds: Vec<Bind> = Vec::new();
    let mut embargoes: Vec<Embargo> = Vec::new();
    let mut key_scopes: Vec<KeyScope> = Vec::new();
    let mut chains: Vec<Chain> = Vec::new();
    let mut holds: Vec<Hold> = Vec::new();
    let mut uniques: Vec<(String, String)> = Vec::new();
    for raw in input.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let p: Vec<&str> = line.split_whitespace().collect();
        match p[0] {
            "KEY" => {
                keys.insert(
                    p[1].to_string(),
                    Key {
                        issuer: p[2].to_string(),
                        subject: p[3].to_string(),
                        not_before: p[4].parse().unwrap(),
                        not_after: p[5].parse().unwrap(),
                        trusted: p[6] == "1",
                    },
                );
            }
            "IMAGE" => images.push(Image {
                name: p[1].to_string(),
                digest: p[2].to_string(),
                env: p[3].to_string(),
                tier: p[4].to_string(),
            }),
            "ATTEST" => {
                let order = attest.len();
                attest.push(Attest {
                    name: p[1].to_string(),
                    digest: p[2].to_string(),
                    predicate: p[3].to_string(),
                    builder: p[4].to_string(),
                    key: p[5].to_string(),
                    timestamp: p[6].parse().unwrap(),
                    log_index: p[7].parse().unwrap(),
                    source_digest: p[8].to_string(),
                    order,
                });
            }
            "LOGROOT" => roots.push(LogRoot {
                log_id: p[1].to_string(),
                root_hash: p[2].to_string(),
                not_before: p[3].parse().unwrap(),
                not_after: p[4].parse().unwrap(),
                trusted: p[5] == "1",
            }),
            "BUNDLE" => bundles.push(Bundle {
                log_index: p[1].parse().unwrap(),
                log_id: p[2].to_string(),
                integrated_time: p[3].parse().unwrap(),
                tree_size: p[4].parse().unwrap(),
                root_hash: p[5].to_string(),
            }),
            "CHECKPOINT" => checkpoints.push(Checkpoint {
                log_id: p[1].to_string(),
                tree_size: p[2].parse().unwrap(),
                root_hash: p[3].to_string(),
                prev_root_hash: p[4].to_string(),
                prev_tree_size: p[5].parse().unwrap(),
                trusted: p[6] == "1",
            }),
            "WITNESS" => witnesses.push(Witness {
                log_id: p[1].to_string(),
                tree_size: p[2].parse().unwrap(),
                root_hash: p[3].to_string(),
                key: p[4].to_string(),
                timestamp: p[5].parse().unwrap(),
                source_digest: p[6].to_string(),
                trusted: p[7] == "1",
            }),
            "WITNESSREQ" => witness_reqs.push(WitnessReq {
                log_id: p[1].to_string(),
                root_prefix: p[2].to_string(),
                min_count: p[3].parse().unwrap(),
                distinct: p[4] == "distinct-key",
                max_age: p[5].parse().unwrap(),
                source_prefix: if p.len() > 6 { p[6].to_string() } else { "*".to_string() },
            }),
            "ROOTPIN" => root_pins.push(RootPin {
                env: p[1].to_string(),
                tier: p[2].to_string(),
                log_id: p[3].to_string(),
                root_prefix: p[4].to_string(),
                not_before: p[5].parse().unwrap(),
                not_after: p[6].parse().unwrap(),
                trusted: p[7] == "1",
            }),
            "SPLITVIEW" => splitviews.push(SplitView {
                log_id: p[1].to_string(),
                tree_size: p[2].parse().unwrap(),
                root_hash: p[3].to_string(),
                trusted: p[4] == "1",
            }),
            "BIND" => binds.push(Bind {
                builder: p[1].to_string(),
                issuer: p[2].to_string(),
                subject_prefix: p[3].to_string(),
                source_prefix: p[4].to_string(),
                env: p[5].to_string(),
                tier: p[6].to_string(),
                not_before: p[7].parse().unwrap(),
                not_after: p[8].parse().unwrap(),
                trusted: p[9] == "1",
            }),
            "EMBARGO" => embargoes.push(Embargo {
                env: p[1].to_string(),
                tier: p[2].to_string(),
                builder: p[3].to_string(),
                source_prefix: p[4].to_string(),
                start: p[5].parse().unwrap(),
                end: p[6].parse().unwrap(),
            }),
            "KEYSCOPE" => key_scopes.push(KeyScope {
                key: p[1].to_string(),
                env: p[2].to_string(),
                tier: p[3].to_string(),
                builder: p[4].to_string(),
                source_prefix: p[5].to_string(),
                not_before: p[6].parse().unwrap(),
                not_after: p[7].parse().unwrap(),
                trusted: p[8] == "1",
            }),
            "HOLD" => holds.push(Hold {
                env: p[1].to_string(),
                tier: p[2].to_string(),
                builder: p[3].to_string(),
                source_prefix: p[4].to_string(),
                marker_predicate: p[5].to_string(),
                marker_builder: p[6].to_string(),
                marker_issuer: p[7].to_string(),
                marker_source_prefix: p[8].to_string(),
                start: p[9].parse().unwrap(),
                end: p[10].parse().unwrap(),
            }),
            "CHAIN" => chains.push(Chain {
                env: p[1].to_string(),
                tier: p[2].to_string(),
                predicate: p[3].to_string(),
                builder: p[4].to_string(),
                prev_predicate: p[5].to_string(),
                prev_builder: p[6].to_string(),
                max_delta: p[7].parse().unwrap(),
                source_prefix: p[8].to_string(),
            }),
            "UNIQUE" => uniques.push((p[1].to_string(), p[2].to_string())),
            "REQUIRE" => policies.push(Policy::Require {
                env: p[1].to_string(),
                tier: p[2].to_string(),
                req: Requirement {
                    predicate: p[3].to_string(),
                    builder: p[4].to_string(),
                    issuer: p[5].to_string(),
                    max_age: p[6].parse().unwrap(),
                    min_log: p[7].parse().unwrap(),
                    subject_prefix: if p.len() > 9 { p[9].to_string() } else { "*".to_string() },
                    source_prefix: if p.len() > 10 { p[10].to_string() } else { "*".to_string() },
                },
                hard: p[8] == "hard",
            }),
            "QUORUM" => policies.push(Policy::Quorum {
                env: p[1].to_string(),
                tier: p[2].to_string(),
                label: p[3].to_string(),
                min_count: p[4].parse().unwrap(),
                distinct: p[5] == "distinct-key",
                min_source_groups: if p.len() > 7 { p[7].parse().unwrap() } else { 0 },
                hard: p[6] == "hard",
            }),
            "MEMBER" => members.entry(p[1].to_string()).or_default().push(Requirement {
                predicate: p[2].to_string(),
                builder: p[3].to_string(),
                issuer: p[4].to_string(),
                max_age: p[5].parse().unwrap(),
                min_log: p[6].parse().unwrap(),
                source_prefix: p[7].to_string(),
                subject_prefix: if p.len() > 8 { p[8].to_string() } else { "*".to_string() },
            }),
            "DELEGATE" => delegates.push(Delegate {
                parent: p[1].to_string(),
                child: p[2].to_string(),
                not_before: p[3].parse().unwrap(),
                not_after: p[4].parse().unwrap(),
                subject_prefix: p[5].to_string(),
                source_prefix: p[6].to_string(),
            }),
            "REQUEST" => requests.push((p[1].to_string(), p[2].to_string(), p[3].parse().unwrap())),
            "REVOKE" => {
                if p.len() == 2 {
                    revokes.push((p[1].to_string(), None, None));
                } else {
                    revokes.push((p[1].to_string(), Some(p[2].parse().unwrap()), Some(p[3].parse().unwrap())));
                }
            }
            "COMPROMISE" => compromises.push((
                p[1].to_string(),
                p[2].parse().unwrap(),
                p[3].parse().unwrap(),
                p[4].to_string(),
            )),
            _ => {}
        }
    }

    let mut decisions = Vec::<(String, String, Vec<String>, Vec<String>)>::new();
    let mut evidence = Vec::<Evidence>::new();
    let mut approved = 0;
    let mut denied = 0;
    let mut warn_count = 0;
    for (name, digest, now) in &requests {
        let rid = format!("{}@{}", name, digest);
        let img = images.iter().find(|i| &i.name == name && &i.digest == digest);
        if img.is_none() {
            decisions.push((rid.clone(), "denied".to_string(), vec!["image-missing".to_string()], Vec::new()));
            denied += 1;
            continue;
        }
        let img = img.unwrap();
        let unique_active = uniques.iter().any(|(env, tier)| env == &img.env && tier == &img.tier);
        let mut used_orders: HashSet<usize> = HashSet::new();
        let mut reasons = Vec::new();
        let mut warns = Vec::new();
        for policy in &policies {
            match policy {
                Policy::Require { env, tier, req, hard } if *env == img.env && *tier == img.tier => {
                    if let Some(a) = best_attestation(
                        name,
                        digest,
                        req,
                        *now,
                        &img.env,
                        &img.tier,
                        &attest,
                        &keys,
                        &revokes,
                        &compromises,
                        &delegates,
                        &roots,
                        &bundles,
                        &checkpoints,
                        &splitviews,
                        &witnesses,
                        &witness_reqs,
                        &root_pins,
                        &binds,
                        &embargoes,
                        &key_scopes,
                        &holds,
                        &chains,
                        if unique_active { Some(&used_orders) } else { None },
                    ) {
                        evidence.push(Evidence {
                            request: rid.clone(),
                            predicate: req.predicate.clone(),
                            builder: req.builder.clone(),
                            key: a.key.clone(),
                            timestamp: a.timestamp,
                            log_index: a.log_index,
                            source_digest: a.source_digest.clone(),
                        });
                        if unique_active {
                            used_orders.insert(a.order);
                        }
                    } else if *hard {
                        reasons.push(format!("missing:{}:{}", req.predicate, req.builder));
                    } else {
                        warns.push(format!("missing:{}:{}", req.predicate, req.builder));
                        warn_count += 1;
                    }
                }
                Policy::Quorum { env, tier, label, min_count, distinct, min_source_groups, hard } if *env == img.env && *tier == img.tier => {
                    if let Some(selected) = select_quorum(
                        name,
                        digest,
                        label,
                        *min_count,
                        *distinct,
                        *min_source_groups,
                        *now,
                        &img.env,
                        &img.tier,
                        &members,
                        &attest,
                        &keys,
                        &revokes,
                        &compromises,
                        &delegates,
                        &roots,
                        &bundles,
                        &checkpoints,
                        &splitviews,
                        &witnesses,
                        &witness_reqs,
                        &root_pins,
                        &binds,
                        &embargoes,
                        &key_scopes,
                        &holds,
                        &chains,
                        if unique_active { Some(&used_orders) } else { None },
                    ) {
                        for (member, a) in selected {
                            if unique_active {
                                used_orders.insert(a.order);
                            }
                            evidence.push(Evidence {
                                request: rid.clone(),
                                predicate: member.predicate,
                                builder: member.builder,
                                key: a.key,
                                timestamp: a.timestamp,
                                log_index: a.log_index,
                                source_digest: a.source_digest,
                            });
                        }
                    } else {
                        let msg = format!("missing:quorum:{}", label);
                        if *hard {
                            reasons.push(msg);
                        } else {
                            warns.push(msg);
                            warn_count += 1;
                        }
                    }
                }
                _ => {}
            }
        }
        if reasons.is_empty() {
            approved += 1;
            decisions.push((rid, "approved".to_string(), reasons, warns));
        } else {
            denied += 1;
            decisions.push((rid, "denied".to_string(), reasons, warns));
        }
    }

    let mut out = String::from("{\"decisions\":[");
    for (i, (rid, status, reasons, warns)) in decisions.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&format!("{{\"request\":{},\"status\":{},\"reasons\":[", js(rid), js(status)));
        for (j, r) in reasons.iter().enumerate() {
            if j > 0 {
                out.push(',');
            }
            out.push_str(&js(r));
        }
        out.push_str("],\"warnings\":[");
        for (j, w) in warns.iter().enumerate() {
            if j > 0 {
                out.push(',');
            }
            out.push_str(&js(w));
        }
        out.push_str("]}");
    }
    out.push_str("],\"evidence\":[");
    for (i, e) in evidence.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&format!(
            "{{\"request\":{},\"predicate\":{},\"builder\":{},\"key\":{},\"timestamp\":{},\"log_index\":{},\"source_digest\":{}}}",
            js(&e.request),
            js(&e.predicate),
            js(&e.builder),
            js(&e.key),
            e.timestamp,
            e.log_index,
            js(&e.source_digest)
        ));
    }
    out.push_str(&format!(
        "],\"summary\":{{\"requests\":{},\"approved\":{},\"denied\":{},\"warnings\":{}}}}}\n",
        requests.len(),
        approved,
        denied,
        warn_count
    ));
    out
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: auditor <input> <output>");
        std::process::exit(2);
    }
    let input = fs::read_to_string(&args[1]).expect("read input");
    fs::create_dir_all(std::path::Path::new(&args[2]).parent().unwrap()).expect("mkdir output");
    fs::write(&args[2], solve(&input)).expect("write output");
}
