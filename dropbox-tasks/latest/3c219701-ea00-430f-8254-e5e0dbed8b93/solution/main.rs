// Meter-fraud forensic auditor for a regional distribution network.
//
// Given a seized evidence corpus -- packed binary meter exports, the regulator's
// circular book, the network registry and the settlement disputes -- it rebuilds the
// revenue that ought to have been billed and surfaces each fraud pattern on the way.
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs;
use std::path::Path;

const FNV_BASIS: u32 = 0x811c9dc5;
const FNV_PRIME: u32 = 0x01000193;
const KINDS: [&str; 8] = [
    "tamper", "spoliation", "misdeclare", "replay", "bypass", "quarantine",
    "void_fraud", "condemnation",
];

fn fnv1a(data: &[u8]) -> String {
    let mut h = FNV_BASIS;
    for b in data {
        h ^= *b as u32;
        h = h.wrapping_mul(FNV_PRIME);
    }
    format!("{:08x}", h)
}

// >>> tiny JSON writer
// a hand-rolled value tree: the report has to be byte-exact and a generic map would
// reorder object keys, so keys are written in declaration order instead.
#[derive(Clone)]
enum Jval {
    S(String),
    I(i64),
    B(bool),
    A(Vec<Jval>),
    O(Vec<(String, Jval)>),
}

fn quote_str(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn render(j: &Jval) -> String {
    match j {
        Jval::S(s) => quote_str(s),
        Jval::I(i) => i.to_string(),
        Jval::B(b) => (if *b { "true" } else { "false" }).to_string(),
        Jval::A(v) => {
            let parts: Vec<String> = v.iter().map(render).collect();
            format!("[{}]", parts.join(","))
        }
        Jval::O(v) => {
            let parts: Vec<String> =
                v.iter().map(|(k, x)| format!("{}:{}", quote_str(k), render(x))).collect();
            format!("{{{}}}", parts.join(","))
        }
    }
}

macro_rules! objrow {
    ($($k:expr => $v:expr),* $(,)?) => { Jval::O(vec![$(($k.to_string(), $v)),*]) };
}

// >>> registry

#[derive(Clone)]
struct Account {
    id: String,
    parent: Option<String>,
    class: i64,
    allowance: i64,
    code: u32,
    serial: String,
}

#[derive(Clone)]
struct Point {
    id: String,
    feeder: String,
    utility: String,
    category: String,
    code: u16,
}

#[derive(Clone)]
struct Band {
    from_kwh: i64,
    rate_cents: i64,
}

#[derive(Clone, Copy)]
struct Shed {
    window_draws: usize,
    enter_kwh: i64,
    exit_kwh: i64,
}

struct Reg {
    util_off: BTreeMap<String, i64>,
    util_by_code: HashMap<u16, String>,
    feeder_util: BTreeMap<String, String>,
    points: BTreeMap<String, Point>,
    point_by_code: HashMap<u16, String>,
    accounts: BTreeMap<String, Account>,
    acct_by_code: HashMap<u32, String>,
    acct_by_serial: HashMap<String, String>,
    bands: Vec<Band>,
    standing: BTreeMap<String, BTreeMap<String, i64>>,
    shed: Shed,
    condemn_threshold: i64,
    penalty_cents: i64,
    replay_window_sec: i64,
    transfer: HashMap<(String, String), i64>,
    chain: HashMap<String, Vec<String>>,
    kids: BTreeMap<String, Vec<String>>,
}

fn home(acct: &str) -> String {
    acct.split('-').next().unwrap_or("").to_string()
}

impl Reg {
    fn load(path: &Path) -> Reg {
        let v: Value = serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
        let mut util_off = BTreeMap::new();
        let mut util_by_code = HashMap::new();
        for u in v["utilities"].as_array().unwrap() {
            let id = u["id"].as_str().unwrap().to_string();
            util_off.insert(id.clone(), u["utc_offset_min"].as_i64().unwrap());
            util_by_code.insert(u["code"].as_i64().unwrap() as u16, id);
        }
        let mut feeder_util = BTreeMap::new();
        for f in v["feeders"].as_array().unwrap() {
            feeder_util.insert(f["id"].as_str().unwrap().to_string(),
                               f["utility"].as_str().unwrap().to_string());
        }
        let mut points = BTreeMap::new();
        let mut point_by_code = HashMap::new();
        for p in v["points"].as_array().unwrap() {
            let pt = Point {
                id: p["id"].as_str().unwrap().to_string(),
                feeder: p["feeder"].as_str().unwrap().to_string(),
                utility: p["utility"].as_str().unwrap().to_string(),
                category: p["category"].as_str().unwrap().to_string(),
                code: p["code"].as_i64().unwrap() as u16,
            };
            point_by_code.insert(pt.code, pt.id.clone());
            points.insert(pt.id.clone(), pt);
        }
        let mut accounts = BTreeMap::new();
        let mut acct_by_code = HashMap::new();
        let mut acct_by_serial = HashMap::new();
        let mut kids: BTreeMap<String, Vec<String>> = BTreeMap::new();
        for a in v["accounts"].as_array().unwrap() {
            let ac = Account {
                id: a["id"].as_str().unwrap().to_string(),
                parent: a["parent"].as_str().map(|s| s.to_string()),
                class: a["class"].as_i64().unwrap(),
                allowance: a["allowance_kwh"].as_i64().unwrap(),
                code: a["code"].as_i64().unwrap() as u32,
                serial: a["serial"].as_str().unwrap().to_string(),
            };
            acct_by_code.insert(ac.code, ac.id.clone());
            acct_by_serial.insert(ac.serial.clone(), ac.id.clone());
            kids.entry(ac.id.clone()).or_default();
            if let Some(p) = &ac.parent {
                kids.entry(p.clone()).or_default().push(ac.id.clone());
            }
            accounts.insert(ac.id.clone(), ac);
        }
        let bands: Vec<Band> = v["bands"].as_array().unwrap().iter()
            .map(|b| Band { from_kwh: b["from_kwh"].as_i64().unwrap(),
                            rate_cents: b["rate_cents"].as_i64().unwrap() })
            .collect();
        let mut standing = BTreeMap::new();
        for (cat, tbl) in v["standing"].as_object().unwrap() {
            let mut m = BTreeMap::new();
            for (k, val) in tbl.as_object().unwrap() {
                m.insert(k.clone(), val.as_i64().unwrap());
            }
            standing.insert(cat.clone(), m);
        }
        let sh = &v["shed"];
        let shed = Shed {
            window_draws: sh["window_draws"].as_i64().unwrap() as usize,
            enter_kwh: sh["enter_kwh"].as_i64().unwrap(),
            exit_kwh: sh["exit_kwh"].as_i64().unwrap(),
        };
        let mut transfer = HashMap::new();
        for t in v["transfer"].as_array().unwrap() {
            let a = t["a"].as_str().unwrap().to_string();
            let b = t["b"].as_str().unwrap().to_string();
            let m = t["min_sec"].as_i64().unwrap();
            transfer.insert((a.clone(), b.clone()), m);
            transfer.insert((b, a), m);
        }
        let mut reg = Reg {
            util_off, util_by_code, feeder_util, points, point_by_code, accounts,
            acct_by_code, acct_by_serial, bands, standing, shed,
            condemn_threshold: v["condemn_threshold"].as_i64().unwrap(),
            penalty_cents: v["penalty_cents"].as_i64().unwrap(),
            replay_window_sec: v["replay_window_sec"].as_i64().unwrap(),
            transfer, chain: HashMap::new(), kids,
        };
        let ids: Vec<String> = reg.accounts.keys().cloned().collect();
        for id in ids {
            let mut out = vec![];
            let mut cur = Some(id.clone());
            while let Some(c) = cur {
                if out.contains(&c) {
                    break;
                }
                out.push(c.clone());
                cur = reg.accounts[&c].parent.clone();
            }
            reg.chain.insert(id, out);
        }
        reg
    }

    fn root(&self, a: &str) -> String {
        self.chain[a].last().unwrap().clone()
    }

    fn subtree(&self, a: &str) -> Vec<String> {
        let mut out = vec![a.to_string()];
        let mut i = 0;
        while i < out.len() {
            if let Some(ch) = self.kids.get(&out[i]) {
                for c in ch {
                    out.push(c.clone());
                }
            }
            i += 1;
        }
        out
    }
}

// >>> segment codec

fn swap_nibbles(b: u8) -> u8 {
    ((b << 4) & 0xf0) | ((b >> 4) & 0x0f)
}

fn checksum(buf: &[u8]) -> u16 {
    let mut acc: u16 = 0;
    let mut i = 0;
    while i < buf.len() {
        let hi = buf[i] as u16;
        let lo = if i + 1 < buf.len() { buf[i + 1] as u16 } else { 0 };
        acc ^= (hi << 8) | lo;
        i += 2;
    }
    ((swap_nibbles((acc >> 8) as u8) as u16) << 8) | (swap_nibbles((acc & 0xff) as u8) as u16)
}

struct RawRec {
    ordinal: i64,
    ok: bool,
    acct_code: u32,
    point_code: u16,
    util_code: u16,
    ts: i64,
    source: usize,
    claimed: i64,
    inspect: bool,
    serial: String,
    kwh: i64,
}

const SOURCES: [&str; 3] = ["telemetry", "estimate", "manual"];

fn parse_segment(buf: &[u8]) -> (Option<u16>, Vec<RawRec>, i64) {
    if buf.len() < 14 || &buf[0..4] != b"MEX1" {
        return (None, vec![], 0);
    }
    let count = u16::from_be_bytes([buf[4], buf[5]]) as usize;
    let base = u32::from_le_bytes([buf[6], buf[7], buf[8], buf[9]]) as i64;
    let mut off = 14usize;
    let mut recs: Vec<RawRec> = vec![];
    while recs.len() < count {
        if off + 14 > buf.len() {
            break;
        }
        let slen = buf[off + 13] as usize;
        let total = 20 + slen;
        if off + total > buf.len() {
            break;
        }
        let raw = &buf[off..off + total];
        let stored = u16::from_be_bytes([raw[total - 2], raw[total - 1]]);
        let mut z = raw.to_vec();
        z[total - 2] = 0;
        z[total - 1] = 0;
        let ok = checksum(&z) == stored;
        let ordinal = recs.len() as i64;
        if ok {
            let flags = raw[12];
            let src = (flags & 0x03) as usize;
            recs.push(RawRec {
                ordinal,
                ok: true,
                acct_code: u32::from_le_bytes([raw[0], raw[1], raw[2], raw[3]]),
                point_code: u16::from_be_bytes([raw[4], raw[5]]),
                util_code: u16::from_le_bytes([raw[6], raw[7]]),
                ts: base + u32::from_le_bytes([raw[8], raw[9], raw[10], raw[11]]) as i64,
                source: if src < 3 { src } else { 2 },
                claimed: ((flags >> 2) & 0x07) as i64,
                inspect: (flags >> 5) & 1 == 1,
                serial: String::from_utf8_lossy(&raw[14..14 + slen]).to_string(),
                kwh: u16::from_be_bytes([raw[14 + slen], raw[15 + slen]]) as i64,
            });
        } else {
            recs.push(RawRec {
                ordinal, ok: false, acct_code: 0, point_code: 0, util_code: 0, ts: 0,
                source: 0, claimed: 0, inspect: false, serial: String::new(), kwh: 0,
            });
        }
        off += total;
    }
    let ucode = recs.iter().find(|r| r.ok).map(|r| r.util_code);
    let lost = count as i64 - recs.len() as i64;
    (ucode, recs, lost)
}

// >>> circulars

#[derive(Clone)]
struct Circular {
    reff: String,
    issuer: String,
    issued: i64,
    start: i64,
    end: Option<i64>,
    supersedes: Vec<String>,
    directives: Vec<String>,
}

fn parse_circular(text: &str) -> Circular {
    let lines: Vec<&str> = text.split('\n').collect();
    let mut head: BTreeMap<String, String> = BTreeMap::new();
    for ln in lines.iter().skip(1) {
        if ln.trim().is_empty() || !ln.contains(':') {
            break;
        }
        let (k, v) = ln.split_once(':').unwrap();
        if k != k.trim()
            || !k.chars().all(|c| c.is_ascii_alphabetic() || c == '-')
            || !k.chars().all(|c| !c.is_ascii_lowercase())
        {
            break;
        }
        head.insert(k.trim().to_string(), v.trim().to_string());
    }
    let mut directives = vec![];
    let mut inblock = false;
    for ln in &lines {
        let s = ln.trim();
        if s == "DIRECTIVES:" {
            inblock = true;
            continue;
        }
        if s == "END DIRECTIVES" {
            inblock = false;
            continue;
        }
        if inblock && !s.is_empty() {
            directives.push(s.to_string());
        }
    }
    let eff = head.get("EFFECTIVE").cloned().unwrap_or_else(|| "0".into());
    let (start, end) = if let Some((a, b)) = eff.split_once(" TO ") {
        (a.trim().parse().unwrap(), Some(b.trim().parse().unwrap()))
    } else {
        (eff.trim().parse().unwrap(), None)
    };
    let supersedes = head.get("SUPERSEDES").map(|s| {
        s.split(',').map(|x| x.trim().to_string()).filter(|x| !x.is_empty()).collect()
    }).unwrap_or_default();
    Circular {
        reff: head["REF"].clone(),
        issuer: head["ISSUER"].clone(),
        issued: head["ISSUED"].parse().unwrap(),
        start, end, supersedes, directives,
    }
}

struct Policy {
    all: BTreeMap<String, Circular>,
    dead: BTreeSet<String>,
    live: Vec<Circular>,
    bands: Vec<Band>,
    standing: BTreeMap<String, BTreeMap<String, i64>>,
    shed: Shed,
}

fn in_force(c: &Circular, t: i64) -> bool {
    match c.end {
        None => t >= c.start,
        Some(e) => c.start <= t && t < e,
    }
}

fn outranks(a: &Circular, sa: i64, b: &Circular, sb: i64) -> bool {
    if sa != sb {
        return sa > sb;
    }
    let ra = (a.issuer == "REGULATOR") as i64;
    let rb = (b.issuer == "REGULATOR") as i64;
    if ra != rb {
        return ra > rb;
    }
    if a.start != b.start {
        return a.start > b.start;
    }
    if a.issued != b.issued {
        return a.issued > b.issued;
    }
    a.reff > b.reff
}

impl Policy {
    fn new(reg: &Reg, circs: Vec<Circular>) -> Policy {
        let mut all = BTreeMap::new();
        for c in &circs {
            all.insert(c.reff.clone(), c.clone());
        }
        let mut dead = BTreeSet::new();
        for c in &circs {
            for t in &c.supersedes {
                if let Some(tc) = all.get(t) {
                    if c.issuer == "REGULATOR" || c.issuer == tc.issuer {
                        dead.insert(t.clone());
                    }
                }
            }
        }
        let live: Vec<Circular> =
            circs.iter().filter(|c| !dead.contains(&c.reff)).cloned().collect();
        Policy { all, dead, live, bands: reg.bands.clone(),
                 standing: reg.standing.clone(), shed: reg.shed }
    }

    fn pick<T, F: Fn(&str) -> Option<(i64, T)>>(&self, t: i64, m: F) -> Option<T> {
        let mut best: Option<(&Circular, T, i64)> = None;
        for c in &self.live {
            if !in_force(c, t) {
                continue;
            }
            for d in &c.directives {
                if let Some((spec, val)) = m(d) {
                    let take = match &best {
                        None => true,
                        Some((bc, _, bs)) => outranks(c, spec, bc, *bs),
                    };
                    if take {
                        best = Some((c, val, spec));
                    }
                }
            }
        }
        best.map(|(_, v, _)| v)
    }

    fn bands_at(&self, root: &str, t: i64) -> Vec<Band> {
        self.pick(t, |d| {
            let p: Vec<&str> = d.split_whitespace().collect();
            if p[0] != "BANDS" || p.len() < 3 {
                return None;
            }
            let spec = if p[1] == root { 1 } else if p[1] == "ALL" { 0 } else { return None };
            let mut rows = vec![];
            for tok in &p[2..] {
                let (a, b) = tok.split_once(':')?;
                rows.push(Band { from_kwh: a.parse().ok()?, rate_cents: b.parse().ok()? });
            }
            Some((spec, rows))
        })
        .unwrap_or_else(|| self.bands.clone())
    }

    fn standing_at(&self, cat: &str, t: i64) -> BTreeMap<String, i64> {
        self.pick(t, |d| {
            let p: Vec<&str> = d.split_whitespace().collect();
            if p[0] != "STANDING" || p.len() < 3 || p[1] != cat {
                return None;
            }
            let mut m = BTreeMap::new();
            for tok in &p[2..] {
                let (a, b) = tok.split_once(':')?;
                m.insert(a.to_string(), b.parse().ok()?);
            }
            Some((0i64, m))
        })
        .unwrap_or_else(|| self.standing[cat].clone())
    }

    fn shed_at(&self, root: &str, t: i64) -> Shed {
        self.pick(t, |d| {
            let p: Vec<&str> = d.split_whitespace().collect();
            if p[0] != "SHED" || p.len() < 8 || p[1] != root {
                return None;
            }
            Some((0i64, Shed { window_draws: p[3].parse().ok()?,
                               enter_kwh: p[5].parse().ok()?,
                               exit_kwh: p[7].parse().ok()? }))
        })
        .unwrap_or(self.shed)
    }

    fn exempt_at(&self, acct: &str, t: i64) -> bool {
        for c in &self.live {
            if !in_force(c, t) {
                continue;
            }
            for d in &c.directives {
                let p: Vec<&str> = d.split_whitespace().collect();
                if p[0] == "EXEMPT" && p.len() >= 2 && p[1] == acct {
                    return true;
                }
            }
        }
        false
    }

    fn basis_state(&self, reff: &str, t: i64) -> String {
        match self.all.get(reff) {
            None => "unknown".into(),
            Some(c) => {
                if self.dead.contains(reff) {
                    "superseded".into()
                } else if !in_force(c, t) {
                    "expired".into()
                } else {
                    "ok".into()
                }
            }
        }
    }
}

// >>> corpus

struct Corpus {
    reg: Reg,
    segs: Vec<(String, Vec<u8>)>,
    circs: Vec<Circular>,
    disputes: Vec<Value>,
}

fn load_corpus(dir: &str) -> Corpus {
    let d = Path::new(dir);
    let reg = Reg::load(&d.join("registry.json"));
    let mut segs = vec![];
    let mut names: Vec<String> = fs::read_dir(d.join("exports")).unwrap()
        .map(|e| e.unwrap().file_name().to_string_lossy().to_string()).collect();
    names.sort();
    for n in names {
        segs.push((n.clone(), fs::read(d.join("exports").join(&n)).unwrap()));
    }
    let mut circs = vec![];
    let cd = d.join("circulars");
    if cd.is_dir() {
        let mut cn: Vec<String> = fs::read_dir(&cd).unwrap()
            .map(|e| e.unwrap().file_name().to_string_lossy().to_string()).collect();
        cn.sort();
        for n in cn {
            circs.push(parse_circular(&fs::read_to_string(cd.join(&n)).unwrap()));
        }
    }
    let mut disputes = vec![];
    let dp = d.join("disputes.jsonl");
    if dp.exists() {
        for line in fs::read_to_string(&dp).unwrap().lines() {
            if !line.trim().is_empty() {
                disputes.push(serde_json::from_str(line).unwrap());
            }
        }
    }
    Corpus { reg, segs, circs, disputes }
}

// >>> stage 1: intake

#[derive(Clone)]
struct Ev {
    segment: String,
    record: i64,
    utility: String,
    account: String,
    point: String,
    ts: i64,
    source: usize,
    class: i64,
    kwh: i64,
    inspect: bool,
}

#[derive(Default, Clone)]
struct Stat {
    reads: i64,
    tamper: i64,
    lost: i64,
    misdeclare: i64,
    flagged: i64,
}

type Findings = BTreeMap<String, Vec<Jval>>;

fn face_cents(reg: &Reg, point: &str, acct: &str, kwh: i64) -> i64 {
    let cat = &reg.points[point].category;
    let cls = reg.accounts[acct].class.to_string();
    kwh * reg.bands[0].rate_cents + reg.standing[cat][&cls]
}

struct Intake {
    evidence: Vec<Ev>,
    stats: BTreeMap<String, Stat>,
    unresolved: i64,
    records: i64,
    segments: i64,
    misdeclare_cents: BTreeMap<String, i64>,
}

fn intake(reg: &Reg, segs: &[(String, Vec<u8>)], f: &mut Findings) -> Intake {
    let mut evidence: Vec<Ev> = vec![];
    let mut stats: BTreeMap<String, Stat> = BTreeMap::new();
    let mut mc: BTreeMap<String, i64> = BTreeMap::new();
    for u in reg.util_off.keys() {
        stats.insert(u.clone(), Stat::default());
        mc.insert(u.clone(), 0);
    }
    let mut unresolved = 0i64;
    let mut nrecords = 0i64;
    for (name, buf) in segs {
        let (ucode, recs, lost) = parse_segment(buf);
        let util = ucode.and_then(|c| reg.util_by_code.get(&c).cloned())
            .unwrap_or_default();
        nrecords += recs.len() as i64;
        for r in &recs {
            if !r.ok {
                if let Some(s) = stats.get_mut(&util) {
                    s.tamper += 1;
                }
                f.get_mut("tamper").unwrap().push(objrow! {
                    "kind" => Jval::S("tamper".into()), "utility" => Jval::S(util.clone()),
                    "segment" => Jval::S(name.clone()), "record" => Jval::I(r.ordinal),
                    "cents" => Jval::I(reg.penalty_cents),
                });
                continue;
            }
            let rutil = reg.util_by_code.get(&r.util_code).cloned().unwrap_or_default();
            if let Some(s) = stats.get_mut(&rutil) {
                s.reads += 1;
                if r.inspect {
                    s.flagged += 1;
                }
            }
            let acct = if r.source == 0 {
                reg.acct_by_code.get(&r.acct_code).cloned()
            } else {
                reg.acct_by_serial.get(&r.serial).cloned()
            };
            let point = reg.point_by_code.get(&r.point_code).cloned();
            let (acct, point) = match (acct, point) {
                (Some(a), Some(p)) => (a, p),
                _ => {
                    unresolved += 1;
                    continue;
                }
            };
            let cat = reg.points[&point].category.clone();
            let rclass = reg.accounts[&acct].class;
            if r.claimed != rclass {
                let base_r = reg.standing[&cat][&rclass.to_string()];
                let base_c = if r.claimed < 1 || r.claimed > 4 {
                    0
                } else {
                    *reg.standing[&cat].get(&r.claimed.to_string()).unwrap_or(&0)
                };
                if let Some(s) = stats.get_mut(&rutil) {
                    s.misdeclare += 1;
                }
                let cents = std::cmp::max(0, base_r - base_c);
                *mc.entry(rutil.clone()).or_default() += cents;
                f.get_mut("misdeclare").unwrap().push(objrow! {
                    "kind" => Jval::S("misdeclare".into()), "utility" => Jval::S(rutil.clone()),
                    "segment" => Jval::S(name.clone()), "record" => Jval::I(r.ordinal),
                    "account" => Jval::S(acct.clone()), "claimed" => Jval::I(r.claimed),
                    "registry" => Jval::I(rclass), "cents" => Jval::I(cents),
                });
            }
            evidence.push(Ev {
                segment: name.clone(), record: r.ordinal, utility: rutil,
                account: acct, point, ts: r.ts, source: r.source, class: r.claimed,
                kwh: r.kwh, inspect: r.inspect,
            });
        }
        if lost > 0 {
            if let Some(s) = stats.get_mut(&util) {
                s.lost += lost;
            }
            f.get_mut("spoliation").unwrap().push(objrow! {
                "kind" => Jval::S("spoliation".into()), "utility" => Jval::S(util.clone()),
                "segment" => Jval::S(name.clone()), "lost" => Jval::I(lost),
                "cents" => Jval::I(lost * reg.penalty_cents),
            });
        }
    }
    evidence.sort_by(|a, b| (&a.segment, a.record).cmp(&(&b.segment, b.record)));
    Intake { evidence, stats, unresolved, records: nrecords,
             segments: segs.len() as i64, misdeclare_cents: mc }
}

fn evidence_text(ev: &[Ev]) -> String {
    let mut s = String::new();
    for e in ev {
        s.push_str(&render(&objrow! {
            "segment" => Jval::S(e.segment.clone()), "record" => Jval::I(e.record),
            "utility" => Jval::S(e.utility.clone()), "account" => Jval::S(e.account.clone()),
            "point" => Jval::S(e.point.clone()), "ts" => Jval::I(e.ts),
            "source" => Jval::S(SOURCES[e.source].into()), "class" => Jval::I(e.class),
            "kwh" => Jval::I(e.kwh), "inspect" => Jval::B(e.inspect),
        }));
        s.push('\n');
    }
    s
}

fn findings_text(f: &Findings) -> String {
    let mut s = String::new();
    for k in KINDS {
        for r in f.get(k).map(|v| v.as_slice()).unwrap_or(&[]) {
            s.push_str(&render(r));
            s.push('\n');
        }
    }
    s
}

fn new_findings() -> Findings {
    let mut f = BTreeMap::new();
    for k in KINDS {
        f.insert(k.to_string(), vec![]);
    }
    f
}

// >>> stage 2: draws

#[derive(Clone)]
struct Draw {
    id: String,
    ts: i64,
    point: String,
    operator: String,
    feeder: String,
    account: String,
    home: String,
    root: String,
    class: i64,
    source: usize,
    reads: i64,
    kwh: i64,
    status: String,
}

fn reconstruct(reg: &Reg, ev: &[Ev]) -> Vec<Draw> {
    let mut groups: BTreeMap<(String, String), Vec<Ev>> = BTreeMap::new();
    for e in ev {
        groups.entry((e.point.clone(), e.account.clone())).or_default().push(e.clone());
    }
    let mut draws = vec![];
    for ((point, acct), mut rs) in groups {
        rs.sort_by(|a, b| (a.ts, a.source, &a.utility).cmp(&(b.ts, b.source, &b.utility)));
        let mut cur: Vec<Ev> = vec![];
        for e in rs {
            if !cur.is_empty() && e.ts - cur[0].ts <= 5 {
                cur.push(e);
            } else {
                if !cur.is_empty() {
                    draws.push(fold(reg, &point, &acct, &cur));
                }
                cur = vec![e];
            }
        }
        if !cur.is_empty() {
            draws.push(fold(reg, &point, &acct, &cur));
        }
    }
    draws.sort_by(|a, b| (a.ts, &a.point, &a.account).cmp(&(b.ts, &b.point, &b.account)));
    draws
}

fn fold(reg: &Reg, point: &str, acct: &str, rs: &[Ev]) -> Draw {
    let owner = reg.points[point].utility.clone();
    let best = rs.iter()
        .min_by_key(|e| (e.source, (e.utility != owner) as i64, e.ts, e.utility.clone()))
        .unwrap();
    Draw {
        id: format!("{}:{}:{}", acct, point, best.ts),
        ts: best.ts,
        point: point.to_string(),
        operator: owner,
        feeder: reg.points[point].feeder.clone(),
        account: acct.to_string(),
        home: home(acct),
        root: reg.root(acct),
        class: reg.accounts[acct].class,
        source: best.source,
        reads: rs.len() as i64,
        kwh: best.kwh,
        status: "ok".into(),
    }
}

fn detect(reg: &Reg, draws: &mut Vec<Draw>, f: &mut Findings) {
    let mut last: HashMap<(String, String), usize> = HashMap::new();
    let mut rep: HashMap<String, (String, i64)> = HashMap::new();
    for i in 0..draws.len() {
        let key = (draws[i].point.clone(), draws[i].account.clone());
        if let Some(&p) = last.get(&key) {
            let gap = draws[i].ts - draws[p].ts;
            if gap < reg.replay_window_sec {
                draws[i].status = "replay".into();
                rep.insert(draws[i].id.clone(), (draws[p].id.clone(), gap));
                continue;
            }
        }
        last.insert(key, i);
    }
    let mut by_acct: BTreeMap<String, Vec<usize>> = BTreeMap::new();
    for (i, d) in draws.iter().enumerate() {
        by_acct.entry(d.account.clone()).or_default().push(i);
    }
    let mut byp: HashMap<String, (String, i64, i64)> = HashMap::new();
    for idxs in by_acct.values() {
        let mut accepted: Option<usize> = None;
        for &i in idxs {
            if draws[i].status == "replay" {
                continue;
            }
            if let Some(a) = accepted {
                if draws[i].point != draws[a].point {
                    let key = (draws[a].point.clone(), draws[i].point.clone());
                    if let Some(&bound) = reg.transfer.get(&key) {
                        let gap = draws[i].ts - draws[a].ts;
                        if gap < bound {
                            draws[i].status = "bypass".into();
                            byp.insert(draws[i].id.clone(),
                                       (draws[a].id.clone(), gap, bound));
                            continue;
                        }
                    }
                }
            }
            accepted = Some(i);
        }
    }
    // replay and bypass findings are emitted in the flagged draw's REGISTER order
    for d in draws.iter() {
        if d.status == "replay" {
            let (prior, gap) = rep[&d.id].clone();
            f.get_mut("replay").unwrap().push(objrow! {
                "kind" => Jval::S("replay".into()), "account" => Jval::S(d.account.clone()),
                "home" => Jval::S(d.home.clone()), "draw" => Jval::S(d.id.clone()),
                "prior" => Jval::S(prior), "gap_sec" => Jval::I(gap),
                "cents" => Jval::I(face_cents(reg, &d.point, &d.account, d.kwh)),
            });
        }
    }
    for d in draws.iter() {
        if d.status == "bypass" {
            let (conflict, gap, bound) = byp[&d.id].clone();
            f.get_mut("bypass").unwrap().push(objrow! {
                "kind" => Jval::S("bypass".into()), "account" => Jval::S(d.account.clone()),
                "home" => Jval::S(d.home.clone()), "draw" => Jval::S(d.id.clone()),
                "conflict" => Jval::S(conflict), "gap_sec" => Jval::I(gap),
                "bound_sec" => Jval::I(bound),
                "cents" => Jval::I(face_cents(reg, &d.point, &d.account, d.kwh)),
            });
        }
    }
    for (acct, idxs) in &by_acct {
        let first = idxs.iter().find(|&&i| draws[i].status == "bypass")
            .map(|&i| draws[i].ts);
        let first = match first {
            None => continue,
            Some(t) => t,
        };
        let mut n = 0i64;
        let mut cents = 0i64;
        for &i in idxs {
            if draws[i].ts >= first && draws[i].status == "ok" {
                draws[i].status = "suspect".into();
                n += 1;
                cents += face_cents(reg, &draws[i].point, acct, draws[i].kwh);
            }
        }
        f.get_mut("quarantine").unwrap().push(objrow! {
            "kind" => Jval::S("quarantine".into()), "account" => Jval::S(acct.clone()),
            "home" => Jval::S(home(acct)), "from_ts" => Jval::I(first), "draws" => Jval::I(n),
            "cents" => Jval::I(cents),
        });
    }
}

fn draws_text(ds: &[Draw]) -> String {
    let mut s = String::new();
    for d in ds {
        s.push_str(&render(&objrow! {
            "id" => Jval::S(d.id.clone()), "ts" => Jval::I(d.ts),
            "point" => Jval::S(d.point.clone()), "operator" => Jval::S(d.operator.clone()),
            "feeder" => Jval::S(d.feeder.clone()), "account" => Jval::S(d.account.clone()),
            "home" => Jval::S(d.home.clone()), "class" => Jval::I(d.class),
            "source" => Jval::S(SOURCES[d.source].into()), "reads" => Jval::I(d.reads),
            "kwh" => Jval::I(d.kwh), "status" => Jval::S(d.status.clone()),
        }));
        s.push('\n');
    }
    s
}

// >>> stage 3: settle

#[derive(Clone)]
struct Row {
    id: String,
    ts: i64,
    point: String,
    operator: String,
    feeder: String,
    account: String,
    home: String,
    root: String,
    class: i64,
    source: usize,
    reads: i64,
    peak: bool,
    shed: bool,
    kwh: i64,
    admitted: i64,
    standing_cents: i64,
    toll_cents: i64,
    charged_cents: i64,
    status: String,
}

fn row_json(r: &Row) -> Jval {
    objrow! {
        "id" => Jval::S(r.id.clone()), "ts" => Jval::I(r.ts), "point" => Jval::S(r.point.clone()),
        "operator" => Jval::S(r.operator.clone()), "feeder" => Jval::S(r.feeder.clone()),
        "account" => Jval::S(r.account.clone()), "home" => Jval::S(r.home.clone()),
        "root" => Jval::S(r.root.clone()), "class" => Jval::I(r.class),
        "source" => Jval::S(SOURCES[r.source].into()), "reads" => Jval::I(r.reads),
        "peak" => Jval::B(r.peak), "shed" => Jval::B(r.shed), "kwh" => Jval::I(r.kwh),
        "admitted" => Jval::I(r.admitted), "standing_cents" => Jval::I(r.standing_cents),
        "toll_cents" => Jval::I(r.toll_cents), "charged_cents" => Jval::I(r.charged_cents),
        "status" => Jval::S(r.status.clone()),
    }
}

fn register_text(rows: &[Row]) -> String {
    let mut s = String::new();
    for r in rows {
        s.push_str(&render(&row_json(r)));
        s.push('\n');
    }
    s
}

fn audit_text(rows: &[Row]) -> String {
    let mut v: Vec<&Row> = rows.iter().collect();
    v.sort_by(|a, b| (&a.account, a.ts, &a.point).cmp(&(&b.account, b.ts, &b.point)));
    let mut s = String::new();
    for r in v {
        s.push_str(&render(&row_json(r)));
        s.push('\n');
    }
    s
}

fn peak_at(ts: i64, off_min: i64) -> bool {
    let t = (ts + off_min * 60).rem_euclid(86400);
    (25200..36000).contains(&t) || (61200..72000).contains(&t)
}

fn energy(bands: &[Band], start: i64, end: i64) -> i64 {
    let mut cost = 0;
    for (i, b) in bands.iter().enumerate() {
        let lo = b.from_kwh;
        let hi = if i + 1 < bands.len() { Some(bands[i + 1].from_kwh) } else { None };
        let a = std::cmp::max(start, lo);
        let z = match hi {
            None => end,
            Some(h) => std::cmp::min(end, h),
        };
        if z > a {
            cost += (z - a) * b.rate_cents;
        }
    }
    cost
}

fn rolling(slots: &[(i64, bool)], window: usize) -> i64 {
    let n = slots.len();
    let from = if n > window { n - window } else { 0 };
    slots[from..].iter().map(|(k, s)| k * if *s { 2 } else { 1 }).sum()
}

fn headroom(reg: &Reg, drawn: &HashMap<String, i64>, acct: &str) -> i64 {
    let mut best = i64::MAX;
    for n in &reg.chain[acct] {
        let r = reg.accounts[n].allowance - drawn[n];
        if r < best {
            best = r;
        }
    }
    std::cmp::max(0, best)
}

fn settle(reg: &Reg, pol: &Policy, draws: &[Draw],
          statuses: &BTreeMap<String, String>) -> Vec<Row> {
    let mut drawn: HashMap<String, i64> = HashMap::new();
    for a in reg.accounts.keys() {
        drawn.insert(a.clone(), 0);
    }
    let mut root_cum: HashMap<String, i64> = HashMap::new();
    let mut shed_on: HashMap<String, bool> = HashMap::new();
    let mut slots: HashMap<String, Vec<(i64, bool)>> = HashMap::new();
    let mut remaining: Vec<usize> = (0..draws.len()).collect();
    let mut rows: Vec<Row> = vec![];
    while !remaining.is_empty() {
        // the settlement order is re-derived after EVERY draw: the next draw to settle
        // is the one whose chain is tightest right now
        let mut bi = 0usize;
        let mut bkey: Option<(i64, i64, String, String)> = None;
        for (pos, &i) in remaining.iter().enumerate() {
            let d = &draws[i];
            let h = headroom(reg, &drawn, &d.account);
            let k = (h, d.ts, d.point.clone(), d.account.clone());
            if bkey.is_none() || k < *bkey.as_ref().unwrap() {
                bkey = Some(k);
                bi = pos;
            }
        }
        let i = remaining.remove(bi);
        let d = &draws[i];
        let hr = bkey.unwrap().0;
        let root = d.root.clone();
        let t = d.ts;
        let bands = pol.bands_at(&root, t);
        let cat = reg.points[&d.point].category.clone();
        let stand_tbl = pol.standing_at(&cat, t);
        let sh = pol.shed_at(&root, t);
        let exempt = pol.exempt_at(&d.account, t);
        slots.entry(root.clone()).or_default();
        shed_on.entry(root.clone()).or_insert(false);
        root_cum.entry(root.clone()).or_insert(0);
        if shed_on[&root] && rolling(&slots[&root], sh.window_draws) < sh.exit_kwh {
            *shed_on.get_mut(&root).unwrap() = false;
        }
        let in_shed = shed_on[&root] && !exempt;
        let admitted = std::cmp::min(d.kwh, hr);
        let start = root_cum[&root];
        let end = start + admitted;
        let standing = stand_tbl[&d.class.to_string()];
        let mut toll = energy(&bands, start, end) + standing;
        let peak = peak_at(t, reg.util_off[&d.operator]);
        if peak {
            toll = toll * 5 / 4;
        }
        if in_shed {
            toll = toll * 3 / 2;
        }
        let status = statuses[&d.id].clone();
        let charged = if status != "ok" {
            slots.get_mut(&root).unwrap().push((0, false));
            0
        } else {
            for n in &reg.chain[&d.account] {
                *drawn.get_mut(n).unwrap() += admitted;
            }
            *root_cum.get_mut(&root).unwrap() = end;
            slots.get_mut(&root).unwrap().push((admitted, in_shed));
            toll
        };
        if !shed_on[&root] && rolling(&slots[&root], sh.window_draws) >= sh.enter_kwh {
            *shed_on.get_mut(&root).unwrap() = true;
        }
        rows.push(Row {
            id: d.id.clone(), ts: t, point: d.point.clone(),
            operator: d.operator.clone(), feeder: d.feeder.clone(),
            account: d.account.clone(), home: d.home.clone(), root,
            class: d.class, source: d.source, reads: d.reads, peak, shed: in_shed,
            kwh: d.kwh, admitted, standing_cents: standing, toll_cents: toll,
            charged_cents: charged, status,
        });
    }
    rows.sort_by(|a, b| (a.ts, &a.point, &a.account).cmp(&(b.ts, &b.point, &b.account)));
    rows
}

fn statuses_for(draws: &[Draw], voided: &BTreeSet<String>,
                condemned: &BTreeSet<String>) -> BTreeMap<String, String> {
    let mut st = BTreeMap::new();
    for d in draws {
        let s = if d.status != "ok" {
            d.status.clone()
        } else if voided.contains(&d.id) {
            "voided".to_string()
        } else if condemned.contains(&d.account) {
            "severed".to_string()
        } else {
            "ok".to_string()
        };
        st.insert(d.id.clone(), s);
    }
    st
}

struct Cascade {
    condemned: BTreeSet<String>,
    feeders: BTreeSet<String>,
    statuses: BTreeMap<String, String>,
}

fn condemn_fixpoint(reg: &Reg, draws: &[Draw], voided: &BTreeSet<String>) -> Cascade {
    // circuits lock out on OWN-EVIDENCE exclusions only; a severance is a consequence
    // of a lockout and never evidence for one
    let base = statuses_for(draws, voided, &BTreeSet::new());
    let mut excl: BTreeMap<String, i64> = BTreeMap::new();
    for d in draws {
        if base[&d.id] != "ok" {
            *excl.entry(d.feeder.clone()).or_default() += 1;
        }
    }
    let feeders: BTreeSet<String> = excl.iter()
        .filter(|(_, n)| **n >= reg.condemn_threshold)
        .map(|(f, _)| f.clone())
        .collect();
    let mut by_acct: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for d in draws {
        by_acct.entry(d.account.clone()).or_default().insert(d.feeder.clone());
    }
    let mut condemned: BTreeSet<String> = BTreeSet::new();
    loop {
        let mut grown = condemned.clone();
        for (a, fs) in &by_acct {
            if !fs.is_empty() && fs.is_subset(&feeders) {
                grown.insert(a.clone());
            }
        }
        for a in grown.clone() {
            for s in reg.subtree(&a) {
                grown.insert(s);
            }
        }
        for a in reg.accounts.keys() {
            let ch = &reg.kids[a];
            if ch.is_empty() || grown.contains(a) {
                continue;
            }
            if ch.iter().all(|c| grown.contains(c)) {
                grown.insert(a.clone());
            }
        }
        if grown == condemned {
            break;
        }
        condemned = grown;
    }
    let statuses = statuses_for(draws, voided, &condemned);
    Cascade { condemned, feeders, statuses }
}

fn adjudicate(pol: &Policy, draws: &[Draw], disputes: &[Value])
    -> (BTreeSet<String>, Vec<(String, String, String, String, String)>) {
    let byid: HashMap<String, &Draw> = draws.iter().map(|d| (d.id.clone(), d)).collect();
    let mut ds: Vec<&Value> = disputes.iter().collect();
    ds.sort_by_key(|d| d["id"].as_str().unwrap().to_string());
    let mut voided = BTreeSet::new();
    let mut frauds = vec![];
    for dp in ds {
        if dp["ruling"].as_str().unwrap() != "upheld" {
            continue;
        }
        let did = dp["draw"].as_str().unwrap().to_string();
        let d = match byid.get(&did) {
            None => continue,
            Some(d) => *d,
        };
        let basis = dp["basis"].as_str().unwrap().to_string();
        let state = pol.basis_state(&basis, d.ts);
        if state == "ok" {
            voided.insert(did);
        } else {
            frauds.push((dp["id"].as_str().unwrap().to_string(),
                         dp["filed_by"].as_str().unwrap().to_string(),
                         did, basis, state));
        }
    }
    (voided, frauds)
}

// >>> reports

fn intake_json(reg: &Reg, it: &Intake, f: &Findings) -> String {
    let mut us: Vec<(i64, String, Jval)> = vec![];
    for (u, s) in &it.stats {
        let leak = it.misdeclare_cents[u];
        let exp = leak + reg.penalty_cents * (s.tamper + s.lost);
        us.push((exp, u.clone(), objrow! {
            "utility" => Jval::S(u.clone()), "reads" => Jval::I(s.reads),
            "tamper" => Jval::I(s.tamper), "lost" => Jval::I(s.lost),
            "misdeclare" => Jval::I(s.misdeclare), "flagged" => Jval::I(s.flagged),
            "leakage_cents" => Jval::I(leak), "exposure_cents" => Jval::I(exp),
        }));
    }
    us.sort_by(|a, b| (-a.0, &a.1).cmp(&(-b.0, &b.1)));
    let three: Vec<(String, Jval)> = KINDS[..3].iter()
        .map(|k| (k.to_string(), Jval::I(f[*k].len() as i64))).collect();
    let nf: i64 = KINDS[..3].iter().map(|k| f[*k].len() as i64).sum();
    render(&objrow! {
        "segments" => Jval::I(it.segments), "records" => Jval::I(it.records),
        "reads" => Jval::I(it.stats.values().map(|s| s.reads).sum()),
        "tampered" => Jval::I(it.stats.values().map(|s| s.tamper).sum()),
        "lost" => Jval::I(it.stats.values().map(|s| s.lost).sum()),
        "unresolved" => Jval::I(it.unresolved), "findings" => Jval::I(nf),
        "findings_by_kind" => Jval::O(three),
        "utilities" => Jval::A(us.into_iter().map(|x| x.2).collect()),
        "evidence_digest" => Jval::S(fnv1a(evidence_text(&it.evidence).as_bytes())),
        "findings_digest" => Jval::S(fnv1a(findings_text(f).as_bytes())),
    })
}

fn draws_json(ds: &[Draw], f: &Findings) -> String {
    let by = |s: &str| Jval::I(ds.iter().filter(|d| d.status == s).count() as i64);
    let six: Vec<(String, Jval)> = KINDS[..6].iter()
        .map(|k| (k.to_string(), Jval::I(f[*k].len() as i64))).collect();
    let nf: i64 = KINDS[..6].iter().map(|k| f[*k].len() as i64).sum();
    let mut comp: Vec<String> = f["quarantine"].iter().map(|j| match j {
        Jval::O(v) => match &v[1].1 { Jval::S(s) => s.clone(), _ => String::new() },
        _ => String::new(),
    }).collect();
    comp.sort();
    render(&objrow! {
        "draws" => Jval::I(ds.len() as i64),
        "excluded" => Jval::I(ds.iter().filter(|d| d.status != "ok").count() as i64),
        "by_status" => objrow! {
            "ok" => by("ok"), "replay" => by("replay"), "bypass" => by("bypass"),
            "suspect" => by("suspect"),
        },
        "compromised_accounts" => Jval::A(comp.into_iter().map(Jval::S).collect()),
        "findings" => Jval::I(nf), "findings_by_kind" => Jval::O(six),
        "draws_digest" => Jval::S(fnv1a(draws_text(ds).as_bytes())),
        "findings_digest" => Jval::S(fnv1a(findings_text(f).as_bytes())),
    })
}

fn jstr(j: &Jval, key: &str) -> String {
    if let Jval::O(v) = j {
        for (k, x) in v {
            if k == key {
                if let Jval::S(s) = x {
                    return s.clone();
                }
            }
        }
    }
    String::new()
}

fn jint(j: &Jval, key: &str) -> i64 {
    if let Jval::O(v) = j {
        for (k, x) in v {
            if k == key {
                if let Jval::I(i) = x {
                    return *i;
                }
            }
        }
    }
    0
}

fn summary_json(reg: &Reg, it: &Intake, rows: &[Row], f: &Findings,
                cas: &Cascade) -> String {
    let mut exposure: Vec<(i64, String, Jval)> = vec![];
    for (u, s) in &it.stats {
        let cnt = |st: &str| rows.iter()
            .filter(|r| r.status == st && r.home == *u).count() as i64;
        let sum_by = |kind: &str, key: &str| -> i64 {
            f[kind].iter().filter(|j| jstr(j, key) == *u).map(|j| jint(j, "cents")).sum()
        };
        let leak = sum_by("misdeclare", "utility") + sum_by("replay", "home")
            + sum_by("bypass", "home") + sum_by("quarantine", "home")
            + sum_by("void_fraud", "filed_by") + sum_by("condemnation", "utility");
        let exp = leak + reg.penalty_cents * (s.tamper + s.lost);
        exposure.push((exp, u.clone(), objrow! {
            "utility" => Jval::S(u.clone()), "reads" => Jval::I(s.reads),
            "tamper" => Jval::I(s.tamper), "lost" => Jval::I(s.lost),
            "misdeclare" => Jval::I(s.misdeclare), "flagged" => Jval::I(s.flagged),
            "replay" => Jval::I(cnt("replay")), "bypass" => Jval::I(cnt("bypass")),
            "suspect" => Jval::I(cnt("suspect")), "severed" => Jval::I(cnt("severed")),
            "void_fraud" => Jval::I(f["void_fraud"].iter()
                .filter(|j| jstr(j, "filed_by") == *u).count() as i64),
            "condemned_feeders" => Jval::I(f["condemnation"].iter()
                .filter(|j| jstr(j, "utility") == *u).count() as i64),
            "leakage_cents" => Jval::I(leak), "exposure_cents" => Jval::I(exp),
        }));
    }
    exposure.sort_by(|a, b| (-a.0, &a.1).cmp(&(-b.0, &b.1)));
    let leak_total: i64 = exposure.iter().map(|e| jint(&e.2, "leakage_cents")).sum();
    let exp_total: i64 = exposure.iter().map(|e| e.0).sum();
    let top = exposure.first().map(|e| e.1.clone()).unwrap_or_default();

    let mut roots: BTreeMap<String, Vec<&Row>> = BTreeMap::new();
    for r in rows {
        roots.entry(r.root.clone()).or_default().push(r);
    }
    let mut supply = vec![];
    for (root, rws) in &roots {
        let ok: Vec<&&Row> = rws.iter().filter(|r| r.status == "ok").collect();
        if ok.is_empty() {
            continue;
        }
        let adm: i64 = ok.iter().map(|r| r.admitted).sum();
        let accts: BTreeSet<String> = rws.iter().map(|r| r.account.clone()).collect();
        supply.push(objrow! {
            "root" => Jval::S(root.clone()), "utility" => Jval::S(home(root)),
            "accounts" => Jval::I(accts.len() as i64), "draws" => Jval::I(rws.len() as i64),
            "admitted_kwh" => Jval::I(adm),
            "charged_cents" => Jval::I(ok.iter().map(|r| r.charged_cents).sum()),
            "shed_draws" => Jval::I(rws.iter().filter(|r| r.shed).count() as i64),
            "final_headroom" => Jval::I(std::cmp::max(0,
                reg.accounts[root].allowance - adm)),
        });
    }
    let kc: Vec<(String, Jval)> = KINDS.iter()
        .map(|k| (k.to_string(), Jval::I(f[*k].len() as i64))).collect();
    let total_findings: i64 = KINDS.iter().map(|k| f[*k].len() as i64).sum();
    let mut comp: Vec<String> = f["quarantine"].iter()
        .map(|j| jstr(j, "account")).collect();
    comp.sort();
    let case = objrow! {
        "draws" => Jval::I(rows.len() as i64),
        "excluded" => Jval::I(rows.iter().filter(|r| r.status != "ok").count() as i64),
        "reads" => Jval::I(it.stats.values().map(|s| s.reads).sum()),
        "tampered" => Jval::I(it.stats.values().map(|s| s.tamper).sum()),
        "lost" => Jval::I(it.stats.values().map(|s| s.lost).sum()),
        "findings" => Jval::I(total_findings), "findings_by_kind" => Jval::O(kc),
        "compromised_accounts" => Jval::A(comp.into_iter().map(Jval::S).collect()),
        "condemned_feeders" => Jval::A(cas.feeders.iter().cloned().map(Jval::S).collect()),
        "severed_accounts" => Jval::A(cas.condemned.iter().cloned().map(Jval::S).collect()),
        "charged_cents" => Jval::I(rows.iter().map(|r| r.charged_cents).sum()),
        "leakage_cents" => Jval::I(leak_total), "exposure_cents" => Jval::I(exp_total),
        "top_utility" => Jval::S(top),
    };
    render(&objrow! {
        "case" => case,
        "exposure" => Jval::A(exposure.into_iter().map(|x| x.2).collect()),
        "supply" => Jval::A(supply),
        "register_digest" => Jval::S(fnv1a(register_text(rows).as_bytes())),
        "audit_digest" => Jval::S(fnv1a(audit_text(rows).as_bytes())),
        "findings_digest" => Jval::S(fnv1a(findings_text(f).as_bytes())),
    })
}

// >>> driver

struct Audit {
    intake: Intake,
    findings: Findings,
    draws: Vec<Draw>,
    rows: Vec<Row>,
    cascade: Cascade,
}

const MAX_STAGE: u32 = 3;

fn run_audit(c: &Corpus, stage: u32) -> Audit {
    let stage = std::cmp::min(stage, MAX_STAGE);
    let mut f = new_findings();
    let it = intake(&c.reg, &c.segs, &mut f);
    let mut draws = vec![];
    let mut rows = vec![];
    let mut cascade = Cascade { condemned: BTreeSet::new(), feeders: BTreeSet::new(),
                                statuses: BTreeMap::new() };
    if stage >= 2 {
        draws = reconstruct(&c.reg, &it.evidence);
        detect(&c.reg, &mut draws, &mut f);
    }
    if stage >= 3 {
        let pol = Policy::new(&c.reg, c.circs.clone());
        let (voided, frauds) = adjudicate(&pol, &draws, &c.disputes);
        cascade = condemn_fixpoint(&c.reg, &draws, &voided);
        rows = settle(&c.reg, &pol, &draws, &cascade.statuses);
        let byid: HashMap<&str, &Row> =
            rows.iter().map(|r| (r.id.as_str(), r)).collect();
        for (id, filed_by, draw, basis, cause) in &frauds {
            f.get_mut("void_fraud").unwrap().push(objrow! {
                "kind" => Jval::S("void_fraud".into()), "dispute" => Jval::S(id.clone()),
                "filed_by" => Jval::S(filed_by.clone()), "draw" => Jval::S(draw.clone()),
                "basis" => Jval::S(basis.clone()), "cause" => Jval::S(cause.clone()),
                "cents" => Jval::I(byid[draw.as_str()].charged_cents),
            });
        }
        for feeder in &cascade.feeders {
            let rws: Vec<&Row> = rows.iter().filter(|r| r.feeder == *feeder).collect();
            let sev: Vec<&&Row> =
                rws.iter().filter(|r| r.status == "severed").collect();
            f.get_mut("condemnation").unwrap().push(objrow! {
                "kind" => Jval::S("condemnation".into()), "feeder" => Jval::S(feeder.clone()),
                "utility" => Jval::S(c.reg.feeder_util[feeder].clone()),
                "excluded" => Jval::I(rws.iter().filter(|r| r.status != "ok").count() as i64),
                "severed" => Jval::I(sev.len() as i64),
                "cents" => Jval::I(sev.iter()
                    .map(|r| face_cents(&c.reg, &r.point, &r.account, r.kwh)).sum()),
            });
        }
    }
    Audit { intake: it, findings: f, draws, rows, cascade }
}

fn arg(args: &[String], key: &str) -> Option<String> {
    let flag = format!("--{}", key);
    for i in 0..args.len() {
        if args[i] == flag && i + 1 < args.len() {
            return Some(args[i + 1].clone());
        }
    }
    None
}

fn need(args: &[String], key: &str) -> String {
    match arg(args, key) {
        Some(v) => v,
        None => {
            eprintln!("missing --{}", key);
            std::process::exit(2);
        }
    }
}

fn write(dir: &str, name: &str, body: &str) {
    fs::create_dir_all(dir).unwrap();
    fs::write(Path::new(dir).join(name), body).unwrap();
}

fn cmd_intake(args: &[String]) {
    let c = load_corpus(&need(args, "data"));
    let out = need(args, "out");
    let a = run_audit(&c, 1);
    write(&out, "evidence.jsonl", &evidence_text(&a.intake.evidence));
    write(&out, "findings.jsonl", &findings_text(&a.findings));
    write(&out, "intake.json",
          &format!("{}\n", intake_json(&c.reg, &a.intake, &a.findings)));
}

fn cmd_draws(args: &[String]) {
    let c = load_corpus(&need(args, "data"));
    let out = need(args, "out");
    let a = run_audit(&c, 2);
    write(&out, "draws.jsonl", &draws_text(&a.draws));
    write(&out, "findings.jsonl", &findings_text(&a.findings));
    write(&out, "draws.json", &format!("{}\n", draws_json(&a.draws, &a.findings)));
}

fn cmd_settle(args: &[String]) {
    let c = load_corpus(&need(args, "data"));
    let out = need(args, "out");
    let a = run_audit(&c, 3);
    write(&out, "register.jsonl", &register_text(&a.rows));
    write(&out, "findings.jsonl", &findings_text(&a.findings));
    write(&out, "summary.json", &format!("{}\n",
        summary_json(&c.reg, &a.intake, &a.rows, &a.findings, &a.cascade)));
}

fn open_db(path: &str) -> rusqlite::Connection {
    let c = rusqlite::Connection::open(path).unwrap();
    c.execute_batch(
        "CREATE TABLE IF NOT EXISTS register (id TEXT PRIMARY KEY, ts INTEGER,
            point TEXT, operator TEXT, feeder TEXT, account TEXT, home TEXT, root TEXT,
            class INTEGER, source TEXT, reads INTEGER, peak INTEGER, shed INTEGER,
            kwh INTEGER, admitted INTEGER, standing_cents INTEGER, toll_cents INTEGER,
            charged_cents INTEGER, status TEXT);
         CREATE TABLE IF NOT EXISTS findings (seq INTEGER PRIMARY KEY, kind TEXT,
            body TEXT);").unwrap();
    c
}

fn cmd_ingest(args: &[String]) {
    let c = load_corpus(&need(args, "data"));
    let db = need(args, "db");
    let a = run_audit(&c, 3);
    let conn = open_db(&db);
    conn.execute("DELETE FROM register", []).unwrap();
    conn.execute("DELETE FROM findings", []).unwrap();
    for r in &a.rows {
        conn.execute(
            "INSERT OR REPLACE INTO register VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,
             ?12,?13,?14,?15,?16,?17,?18,?19)",
            rusqlite::params![r.id, r.ts, r.point, r.operator, r.feeder, r.account,
                r.home, r.root, r.class, SOURCES[r.source], r.reads, r.peak as i64,
                r.shed as i64, r.kwh, r.admitted, r.standing_cents, r.toll_cents,
                r.charged_cents, r.status]).unwrap();
    }
    let mut seq = 0i64;
    for k in KINDS {
        for j in &a.findings[k] {
            conn.execute("INSERT OR REPLACE INTO findings VALUES (?1,?2,?3)",
                         rusqlite::params![seq, k, render(j)]).unwrap();
            seq += 1;
        }
    }
}

fn db_rows(conn: &rusqlite::Connection) -> Vec<(i64, String, Jval)> {
    let mut stmt = conn.prepare(
        "SELECT id,ts,point,operator,feeder,account,home,root,class,source,reads,peak,
         shed,kwh,admitted,standing_cents,toll_cents,charged_cents,status FROM register")
        .unwrap();
    let out = stmt.query_map([], |r| {
        let ts: i64 = r.get(1)?;
        let id: String = r.get(0)?;
        let charged: i64 = r.get(17)?;
        let point: String = r.get(2)?;
        let account: String = r.get(5)?;
        let src: String = r.get(9)?;
        Ok((charged, format!("{}|{}|{}", ts, point, account), objrow! {
            "id" => Jval::S(id), "ts" => Jval::I(ts), "point" => Jval::S(point.clone()),
            "operator" => Jval::S(r.get::<_, String>(3)?),
            "feeder" => Jval::S(r.get::<_, String>(4)?),
            "account" => Jval::S(account.clone()),
            "home" => Jval::S(r.get::<_, String>(6)?),
            "root" => Jval::S(r.get::<_, String>(7)?),
            "class" => Jval::I(r.get::<_, i64>(8)?), "source" => Jval::S(src),
            "reads" => Jval::I(r.get::<_, i64>(10)?),
            "peak" => Jval::B(r.get::<_, i64>(11)? != 0),
            "shed" => Jval::B(r.get::<_, i64>(12)? != 0),
            "kwh" => Jval::I(r.get::<_, i64>(13)?),
            "admitted" => Jval::I(r.get::<_, i64>(14)?),
            "standing_cents" => Jval::I(r.get::<_, i64>(15)?),
            "toll_cents" => Jval::I(r.get::<_, i64>(16)?),
            "charged_cents" => Jval::I(charged),
            "status" => Jval::S(r.get::<_, String>(18)?),
        }))
    }).unwrap().filter_map(|x| x.ok()).collect();
    out
}

fn handle(db: &str, url: &str) -> (u16, String) {
    let path = url.split('?').next().unwrap_or("").to_string();
    let query = url.split('?').nth(1).unwrap_or("").to_string();
    let conn = open_db(db);
    if path == "/register" {
        let mut min_charge: Option<i64> = None;
        let mut want_status: Option<String> = None;
        for kv in query.split('&') {
            if let Some(v) = kv.strip_prefix("min_charge=") {
                min_charge = v.parse().ok();
            }
            if let Some(v) = kv.strip_prefix("status=") {
                want_status = Some(v.to_string());
            }
        }
        let mut rows = db_rows(&conn);
        rows.sort_by(|a, b| {
            let ka: Vec<&str> = a.1.split('|').collect();
            let kb: Vec<&str> = b.1.split('|').collect();
            (ka[0].parse::<i64>().unwrap(), ka[1], ka[2])
                .cmp(&(kb[0].parse::<i64>().unwrap(), kb[1], kb[2]))
        });
        let keep: Vec<Jval> = rows.into_iter()
            .filter(|(charged, _, j)| {
                min_charge.map(|m| *charged >= m).unwrap_or(true)
                    && want_status.as_ref().map(|s| jstr(j, "status") == *s).unwrap_or(true)
            })
            .map(|(_, _, j)| j)
            .collect();
        let n = keep.len() as i64;
        return (200, render(&objrow! { "register" => Jval::A(keep), "count" => Jval::I(n) }));
    }
    if let Some(rest) = path.strip_prefix("/register/") {
        for (_, _, j) in db_rows(&conn) {
            if jstr(&j, "id") == rest {
                return (200, render(&j));
            }
        }
        return (404, render(&objrow! { "error" => Jval::S("unknown draw".into()) }));
    }
    if path == "/findings" {
        let want = query.strip_prefix("kind=").map(|s| s.to_string());
        let mut stmt = conn.prepare(
            "SELECT seq,kind,body FROM findings ORDER BY seq").unwrap();
        let rows: Vec<(String, String)> = stmt.query_map([], |r| {
            Ok((r.get::<_, String>(1)?, r.get::<_, String>(2)?))
        }).unwrap().filter_map(|x| x.ok()).collect();
        let keep: Vec<String> = rows.into_iter()
            .filter(|(k, _)| want.as_ref().map(|w| k == w).unwrap_or(true))
            .map(|(_, b)| b).collect();
        let body = format!("{{\"findings\":[{}],\"count\":{}}}",
                           keep.join(","), keep.len());
        return (200, body);
    }
    (404, render(&objrow! { "error" => Jval::S("not found".into()) }))
}

fn cmd_serve(args: &[String]) {
    let db = need(args, "db");
    let port = need(args, "port");
    let server = tiny_http::Server::http(format!("127.0.0.1:{}", port)).unwrap();
    for req in server.incoming_requests() {
        let url = req.url().to_string();
        let (code, body) = handle(&db, &url);
        let hdr = "Content-Type: application/json".parse::<tiny_http::Header>().unwrap();
        let resp = tiny_http::Response::from_string(body)
            .with_status_code(code).with_header(hdr);
        let _ = req.respond(resp);
    }
}

fn main() {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    if argv.is_empty() {
        eprintln!("usage: tariff <command> [flags]");
        std::process::exit(2);
    }
    let rest = &argv[1..];
    match argv[0].as_str() {
        "intake" => cmd_intake(rest),
        "draws" => cmd_draws(rest),
        "settle" => cmd_settle(rest),
        "ingest" => cmd_ingest(rest),
        "serve" => cmd_serve(rest),
        other => {
            eprintln!("unknown command: {}", other);
            std::process::exit(2);
        }
    }
}
