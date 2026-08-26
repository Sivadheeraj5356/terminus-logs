use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Eq, PartialEq, Ord, PartialOrd)]
struct Version(u64, u64, u64);

impl Version {
    fn parse(s: &str) -> Option<Self> {
        let parts: Vec<&str> = s.split('.').collect();
        if parts.len() != 3 || parts.iter().any(|p| p.is_empty()) {
            return None;
        }
        Some(Self(
            parts[0].parse().ok()?,
            parts[1].parse().ok()?,
            parts[2].parse().ok()?,
        ))
    }

    fn code(&self) -> u64 {
        self.0 * 1_000_000 + self.1 * 1_000 + self.2
    }

    fn text(&self) -> String {
        format!("{}.{}.{}", self.0, self.1, self.2)
    }
}

#[derive(Clone, Debug)]
struct Requirement {
    condition: Option<(String, bool)>,
    cap: String,
    abi: Option<u64>,
    lo: Option<Version>,
    hi: Option<Version>,
}

#[derive(Clone, Debug)]
struct Provide {
    cap: String,
    abi: u64,
}

#[derive(Clone, Debug)]
enum Conflict {
    Name(String),
    Cap(String, Option<u64>),
}

#[derive(Clone, Debug)]
struct Release {
    name: String,
    version: Version,
    targets: Vec<String>,
    provides: Vec<Provide>,
    requires: Vec<Requirement>,
    conflicts: Vec<Conflict>,
    toolchain: u64,
    source: u64,
    image: u64,
    risk: u64,
    cached: bool,
    segment: u64,
    line: usize,
    file: String,
}

#[derive(Clone, Debug)]
struct Policy {
    target: String,
    flags: BTreeSet<String>,
    toolchain_max: u64,
    source_budget: u64,
    image_budget: u64,
    risk_budget: u64,
}

#[derive(Clone)]
struct Plan {
    releases: Vec<Release>,
    freshness: u64,
    source: u64,
    image: u64,
    risk: u64,
    signature: String,
}

fn token(s: &str) -> bool {
    !s.is_empty()
        && s.bytes().all(|b| {
            b.is_ascii_lowercase()
                || b.is_ascii_digit()
                || b == b'.'
                || b == b'_'
                || b == b'-'
        })
}

fn active_line(line: &str) -> Option<&str> {
    let trimmed = line.trim_matches(|c: char| c.is_ascii_whitespace());
    if trimmed.is_empty() || trimmed.starts_with('#') {
        None
    } else {
        Some(trimmed)
    }
}

fn parse_provide(s: &str) -> Option<Provide> {
    let (cap, abi) = s.rsplit_once('@')?;
    if !token(cap) {
        return None;
    }
    Some(Provide {
        cap: cap.to_string(),
        abi: abi.parse().ok()?,
    })
}

fn parse_requirement(s: &str) -> Option<Requirement> {
    let (condition, atom) = if let Some(pos) = s.find('?') {
        let raw = &s[..pos];
        let atom = &s[pos + 1..];
        if let Some(flag) = raw.strip_prefix('!') {
            if !token(flag) {
                return None;
            }
            (Some((flag.to_string(), false)), atom)
        } else {
            if !token(raw) {
                return None;
            }
            (Some((raw.to_string(), true)), atom)
        }
    } else {
        (None, s)
    };
    let (cap_abi, range) = atom.split_once('#')?;
    let (cap, abi_s) = cap_abi.rsplit_once('@')?;
    let (lo_s, hi_s) = range.split_once("..")?;
    if !token(cap) {
        return None;
    }
    let abi = if abi_s == "*" {
        None
    } else {
        Some(abi_s.parse().ok()?)
    };
    let lo = if lo_s == "*" {
        None
    } else {
        Some(Version::parse(lo_s)?)
    };
    let hi = if hi_s == "*" {
        None
    } else {
        Some(Version::parse(hi_s)?)
    };
    if matches!((&lo, &hi), (Some(a), Some(b)) if a > b) {
        return None;
    }
    Some(Requirement {
        condition,
        cap: cap.to_string(),
        abi,
        lo,
        hi,
    })
}

fn parse_conflict(s: &str) -> Option<Conflict> {
    if let Some((cap, abi_s)) = s.rsplit_once('@') {
        if !token(cap) {
            return None;
        }
        let abi = if abi_s == "*" {
            None
        } else {
            Some(abi_s.parse().ok()?)
        };
        Some(Conflict::Cap(cap.to_string(), abi))
    } else if token(s) {
        Some(Conflict::Name(s.to_string()))
    } else {
        None
    }
}

fn parse_csv<T, F>(s: &str, mut parser: F) -> Option<Vec<T>>
where
    F: FnMut(&str) -> Option<T>,
{
    if s == "-" {
        return Some(Vec::new());
    }
    let mut out = Vec::new();
    for item in s.split(',') {
        if item.is_empty() {
            return None;
        }
        out.push(parser(item)?);
    }
    Some(out)
}

fn parse_release(
    text: &str,
    segment: u64,
    line: usize,
    file: &str,
) -> Option<Release> {
    let fields: Vec<&str> = text.split('|').map(str::trim).collect();
    if fields.len() != 11 || !token(fields[0]) {
        return None;
    }
    let version = Version::parse(fields[1])?;
    let targets = if fields[2] == "*" {
        vec!["*".to_string()]
    } else {
        let values: Vec<String> = fields[2].split(',').map(str::to_string).collect();
        if values.is_empty() || values.iter().any(|v| !token(v)) {
            return None;
        }
        values
    };
    let provides = parse_csv(fields[3], parse_provide)?;
    if provides.is_empty() {
        return None;
    }
    let requires = parse_csv(fields[4], parse_requirement)?;
    let conflicts = parse_csv(fields[5], parse_conflict)?;
    let toolchain = fields[6].parse().ok()?;
    let source = fields[7].parse().ok()?;
    let image = fields[8].parse().ok()?;
    let risk = fields[9].parse().ok()?;
    let cached = match fields[10] {
        "yes" => true,
        "no" => false,
        _ => return None,
    };
    Some(Release {
        name: fields[0].to_string(),
        version,
        targets,
        provides,
        requires,
        conflicts,
        toolchain,
        source,
        image,
        risk,
        cached,
        segment,
        line,
        file: file.to_string(),
    })
}

fn segment_id(name: &str) -> Option<u64> {
    if !name.ends_with(".pkg") {
        return None;
    }
    let rest = name.strip_prefix("seg_")?;
    let digits: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
    if digits.is_empty() {
        None
    } else {
        digits.parse().ok()
    }
}

fn load_policy(dir: &Path) -> Result<Policy, String> {
    let text = fs::read_to_string(dir.join("policy.cfg")).map_err(|e| e.to_string())?;
    let mut values = BTreeMap::new();
    for line in text.lines() {
        if let Some(line) = active_line(line) {
            let (key, value) = line.split_once('=').ok_or("bad policy")?;
            values.insert(key.trim().to_string(), value.trim().to_string());
        }
    }
    let target = values.remove("target").ok_or("missing target")?;
    if !token(&target) {
        return Err("bad target".into());
    }
    let flags_s = values.remove("flags").ok_or("missing flags")?;
    let mut flags = BTreeSet::new();
    if flags_s != "-" {
        for flag in flags_s.split(',') {
            if !token(flag) {
                return Err("bad flag".into());
            }
            flags.insert(flag.to_string());
        }
    }
    Ok(Policy {
        target,
        flags,
        toolchain_max: values
            .remove("toolchain_max")
            .ok_or("missing toolchain")?
            .parse()
            .map_err(|_| "bad toolchain")?,
        source_budget: values
            .remove("source_budget")
            .ok_or("missing source")?
            .parse()
            .map_err(|_| "bad source")?,
        image_budget: values
            .remove("image_budget")
            .ok_or("missing image")?
            .parse()
            .map_err(|_| "bad image")?,
        risk_budget: values
            .remove("risk_budget")
            .ok_or("missing risk")?
            .parse()
            .map_err(|_| "bad risk")?,
    })
}

fn load_roots(dir: &Path) -> Result<Vec<Requirement>, String> {
    let text = fs::read_to_string(dir.join("roots.req")).map_err(|e| e.to_string())?;
    let mut roots = Vec::new();
    for line in text.lines() {
        if let Some(line) = active_line(line) {
            let req = parse_requirement(line).ok_or("bad root")?;
            if req.condition.is_some() {
                return Err("conditional root".into());
            }
            roots.push(req);
        }
    }
    Ok(roots)
}

fn load_groups(dir: &Path, policy: &Policy) -> Result<Vec<Vec<Release>>, String> {
    let registry = dir.join("registry");
    let mut files: Vec<(String, PathBuf, u64)> = Vec::new();
    for entry in fs::read_dir(registry).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        if !entry.file_type().map_err(|e| e.to_string())?.is_file() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().to_string();
        if let Some(segment) = segment_id(&name) {
            files.push((name, entry.path(), segment));
        }
    }
    files.sort_by(|a, b| a.0.cmp(&b.0));

    let mut kept: BTreeMap<(String, Version), Release> = BTreeMap::new();
    for (file, path, segment) in files {
        let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
        for (index, raw) in text.lines().enumerate() {
            let line_no = index + 1;
            let Some(line) = active_line(raw) else {
                continue;
            };
            let Some(row) = parse_release(line, segment, line_no, &file) else {
                continue;
            };
            let key = (row.name.clone(), row.version.clone());
            let replace = match kept.get(&key) {
                None => true,
                Some(old) => {
                    row.segment > old.segment
                        || (row.segment == old.segment && row.line > old.line)
                        || (row.segment == old.segment
                            && row.line == old.line
                            && row.file < old.file)
                }
            };
            if replace {
                kept.insert(key, row);
            }
        }
    }

    let mut by_name: BTreeMap<String, Vec<Release>> = BTreeMap::new();
    for row in kept.into_values() {
        if row.toolchain <= policy.toolchain_max
            && row
                .targets
                .iter()
                .any(|target| target == "*" || target == &policy.target)
        {
            by_name.entry(row.name.clone()).or_default().push(row);
        }
    }
    for rows in by_name.values_mut() {
        rows.sort_by(|a, b| a.version.cmp(&b.version));
    }
    Ok(by_name.into_values().collect())
}

fn requirement_active(req: &Requirement, policy: &Policy) -> bool {
    match &req.condition {
        None => true,
        Some((flag, wanted)) => policy.flags.contains(flag) == *wanted,
    }
}

fn requirement_satisfied(req: &Requirement, selected: &[Release]) -> bool {
    selected.iter().any(|release| {
        let version_ok = req.lo.as_ref().map_or(true, |lo| &release.version >= lo)
            && req.hi.as_ref().map_or(true, |hi| &release.version <= hi);
        version_ok
            && release.provides.iter().any(|provide| {
                provide.cap == req.cap && req.abi.map_or(true, |abi| abi == provide.abi)
            })
    })
}

fn feasible(selected: &[Release], policy: &Policy, roots: &[Requirement]) -> bool {
    let source: u64 = selected
        .iter()
        .map(|r| if r.cached { 0 } else { r.source })
        .sum();
    let image: u64 = selected.iter().map(|r| r.image).sum();
    let risk: u64 = selected.iter().map(|r| r.risk).sum();
    if source > policy.source_budget
        || image > policy.image_budget
        || risk > policy.risk_budget
    {
        return false;
    }

    let mut abi_by_cap: BTreeMap<&str, u64> = BTreeMap::new();
    for release in selected {
        for provide in &release.provides {
            match abi_by_cap.get(provide.cap.as_str()) {
                Some(old) if *old != provide.abi => return false,
                _ => {
                    abi_by_cap.insert(provide.cap.as_str(), provide.abi);
                }
            }
        }
    }

    if roots
        .iter()
        .any(|req| !requirement_satisfied(req, selected))
    {
        return false;
    }
    for release in selected {
        for req in &release.requires {
            if requirement_active(req, policy) && !requirement_satisfied(req, selected) {
                return false;
            }
        }
    }

    for (i, release) in selected.iter().enumerate() {
        for conflict in &release.conflicts {
            for (j, other) in selected.iter().enumerate() {
                if i == j {
                    continue;
                }
                let hit = match conflict {
                    Conflict::Name(name) => &other.name == name,
                    Conflict::Cap(cap, abi) => other.provides.iter().any(|provide| {
                        &provide.cap == cap && abi.map_or(true, |wanted| wanted == provide.abi)
                    }),
                };
                if hit {
                    return false;
                }
            }
        }
    }
    true
}

fn make_plan(selected: &[Release]) -> Plan {
    let mut releases = selected.to_vec();
    releases.sort_by(|a, b| a.name.cmp(&b.name));
    let freshness = releases.iter().map(|r| r.version.code()).sum();
    let source = releases
        .iter()
        .map(|r| if r.cached { 0 } else { r.source })
        .sum();
    let image = releases.iter().map(|r| r.image).sum();
    let risk = releases.iter().map(|r| r.risk).sum();
    let signature = releases
        .iter()
        .map(|r| format!("{}@{}", r.name, r.version.text()))
        .collect::<Vec<_>>()
        .join(",");
    Plan {
        releases,
        freshness,
        source,
        image,
        risk,
        signature,
    }
}

fn requirement_possible(
    req: &Requirement,
    selected: &[Release],
    groups: &[Vec<Release>],
    index: usize,
) -> bool {
    requirement_satisfied(req, selected)
        || groups[index..].iter().flatten().any(|release| {
            let version_ok = req.lo.as_ref().map_or(true, |lo| &release.version >= lo)
                && req.hi.as_ref().map_or(true, |hi| &release.version <= hi);
            version_ok
                && release.provides.iter().any(|provide| {
                    provide.cap == req.cap && req.abi.map_or(true, |abi| abi == provide.abi)
                })
        })
}

fn partial_requirements_possible(
    selected: &[Release],
    policy: &Policy,
    roots: &[Requirement],
    groups: &[Vec<Release>],
    index: usize,
) -> bool {
    roots
        .iter()
        .all(|req| requirement_possible(req, selected, groups, index))
        && selected.iter().all(|release| {
            release.requires.iter().all(|req| {
                !requirement_active(req, policy)
                    || requirement_possible(req, selected, groups, index)
            })
        })
}

fn better(candidate: &Plan, old: Option<&Plan>) -> bool {
    let Some(old) = old else {
        return true;
    };
    candidate.releases.len() < old.releases.len()
        || (candidate.releases.len() == old.releases.len()
            && (candidate.freshness > old.freshness
                || (candidate.freshness == old.freshness
                    && (candidate.source < old.source
                        || (candidate.source == old.source
                            && (candidate.image < old.image
                                || (candidate.image == old.image
                                    && (candidate.risk < old.risk
                                        || (candidate.risk == old.risk
                                            && candidate.signature < old.signature)))))))))
}

fn enumerate(
    groups: &[Vec<Release>],
    index: usize,
    selected: &mut Vec<Release>,
    policy: &Policy,
    roots: &[Requirement],
    best: &mut Option<Plan>,
    source: u64,
    image: u64,
    risk: u64,
) {
    if source > policy.source_budget
        || image > policy.image_budget
        || risk > policy.risk_budget
    {
        return;
    }
    if !partial_requirements_possible(selected, policy, roots, groups, index) {
        return;
    }
    if index == groups.len() {
        if feasible(selected, policy, roots) {
            let plan = make_plan(selected);
            if better(&plan, best.as_ref()) {
                *best = Some(plan);
            }
        }
        return;
    }

    enumerate(
        groups,
        index + 1,
        selected,
        policy,
        roots,
        best,
        source,
        image,
        risk,
    );
    for release in &groups[index] {
        selected.push(release.clone());
        enumerate(
            groups,
            index + 1,
            selected,
            policy,
            roots,
            best,
            source + if release.cached { 0 } else { release.source },
            image + release.image,
            risk + release.risk,
        );
        selected.pop();
    }
}

fn render(plan: Option<Plan>) -> String {
    let Some(plan) = plan else {
        return "UNSAT\n".to_string();
    };
    let mut out = format!(
        "TOTAL|{}|{}|{}|{}|{}\n",
        plan.releases.len(),
        plan.freshness,
        plan.source,
        plan.image,
        plan.risk
    );
    for release in plan.releases {
        out.push_str(&format!(
            "LOCK|{}|{}|{}|{}|{}\n",
            release.name,
            release.version.text(),
            release.segment,
            release.line,
            if release.cached { "yes" } else { "no" }
        ));
    }
    out
}

fn run(input: &Path, output: &Path) -> Result<(), String> {
    let policy = load_policy(input)?;
    let roots = load_roots(input)?;
    let groups = load_groups(input, &policy)?;
    let mut best = None;
    enumerate(
        &groups,
        0,
        &mut Vec::new(),
        &policy,
        &roots,
        &mut best,
        0,
        0,
        0,
    );
    if let Some(parent) = output.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
    }
    fs::write(output, render(best)).map_err(|e| e.to_string())
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut input = None;
    let mut output = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--input" if i + 1 < args.len() => {
                input = Some(PathBuf::from(&args[i + 1]));
                i += 2;
            }
            "--output" if i + 1 < args.len() => {
                output = Some(PathBuf::from(&args[i + 1]));
                i += 2;
            }
            _ => {
                eprintln!("usage: linkseal --input DIR --output FILE");
                std::process::exit(2);
            }
        }
    }
    let (Some(input), Some(output)) = (input, output) else {
        eprintln!("usage: linkseal --input DIR --output FILE");
        std::process::exit(2);
    };
    if let Err(error) = run(&input, &output) {
        eprintln!("linkseal: {}", error);
        std::process::exit(1);
    }
}
