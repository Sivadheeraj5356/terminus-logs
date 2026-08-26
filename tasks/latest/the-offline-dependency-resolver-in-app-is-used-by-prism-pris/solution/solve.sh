#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > src/main.rs <<'RS'
use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone, Eq, PartialEq, Debug)]
struct Version {
    raw: String,
    nums: [u64; 3],
    pre: Option<String>,
}

impl Version {
    fn parse(s: &str) -> Result<Self, String> {
        let (core, pre) = match s.split_once('-') {
            Some((core, pre)) if !pre.is_empty() => (core, Some(pre.to_string())),
            Some(_) => return Err(format!("bad version {s}")),
            None => (s, None),
        };
        let parts: Vec<_> = core.split('.').collect();
        if parts.len() != 3 {
            return Err(format!("bad version {s}"));
        }
        let mut nums = [0u64; 3];
        for (idx, part) in parts.iter().enumerate() {
            nums[idx] = part.parse().map_err(|_| format!("bad version {s}"))?;
        }
        Ok(Self { raw: s.to_string(), nums, pre })
    }
}

impl Ord for Version {
    fn cmp(&self, other: &Self) -> Ordering {
        match self.nums.cmp(&other.nums) {
            Ordering::Equal => match (&self.pre, &other.pre) {
                (None, None) => Ordering::Equal,
                (None, Some(_)) => Ordering::Greater,
                (Some(_), None) => Ordering::Less,
                (Some(a), Some(b)) => a.cmp(b),
            },
            ord => ord,
        }
    }
}

impl PartialOrd for Version {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[derive(Clone)]
struct Requirement {
    package: String,
    constraint: String,
    features: BTreeSet<String>,
}

#[derive(Clone)]
struct VersionRecord {
    version: Version,
    yanked: bool,
    deps: Vec<Requirement>,
    feature_deps: BTreeMap<String, Vec<Requirement>>,
}

#[derive(Default)]
struct Options {
    workspace: String,
    registry: String,
    lock: String,
    report: String,
}

fn main() {
    match real_main() {
        Ok(code) => std::process::exit(code),
        Err((code, msg)) => {
            eprintln!("{msg}");
            std::process::exit(code);
        }
    }
}

fn real_main() -> Result<i32, (i32, String)> {
    let opts = parse_args().map_err(|e| (2, e))?;
    validate_inputs(&opts).map_err(|e| (2, e))?;
    let roots = parse_workspace(Path::new(&opts.workspace)).map_err(|e| (2, e))?;
    match resolve(&opts, roots) {
        Ok(lock_json) => {
            let report_json = "{\n  \"conflicts\": []\n}\n".to_string();
            write_output(&opts.report, &report_json).map_err(|e| (1, e))?;
            write_output(&opts.lock, &lock_json).map_err(|e| (1, e))?;
            Ok(0)
        }
        Err(conflicts) => {
            let report = conflict_report(&conflicts);
            write_output(&opts.report, &report).map_err(|e| (1, e))?;
            Ok(2)
        }
    }
}

fn parse_args() -> Result<Options, String> {
    let mut opts = Options::default();
    let mut args = env::args().skip(1);
    while let Some(flag) = args.next() {
        let value = args.next().ok_or_else(|| format!("missing value for {flag}"))?;
        match flag.as_str() {
            "--workspace" => opts.workspace = value,
            "--registry" => opts.registry = value,
            "--lock" => opts.lock = value,
            "--report" => opts.report = value,
            _ => return Err(format!("unknown flag {flag}")),
        }
    }
    if opts.workspace.is_empty() || opts.registry.is_empty() || opts.lock.is_empty() || opts.report.is_empty() {
        return Err("prism-dependency-forge --workspace <absolute-file> --registry <absolute-dir> --lock <absolute-file> --report <absolute-file>".to_string());
    }
    for path in [&opts.workspace, &opts.registry, &opts.lock, &opts.report] {
        if !PathBuf::from(path).is_absolute() {
            return Err("all paths must be absolute".to_string());
        }
    }
    Ok(opts)
}

fn validate_inputs(opts: &Options) -> Result<(), String> {
    if !Path::new(&opts.workspace).is_file() {
        return Err("workspace file does not exist".to_string());
    }
    if !Path::new(&opts.registry).is_dir() {
        return Err("registry directory does not exist".to_string());
    }
    Ok(())
}

fn parse_workspace(path: &Path) -> Result<Vec<Requirement>, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut roots = Vec::new();
    for (line_no, raw) in text.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<_> = line.split_whitespace().collect();
        if parts.len() < 4 || parts[0] != "root" {
            return Err(format!("bad workspace line {}", line_no + 1));
        }
        let mut features = BTreeSet::new();
        for token in &parts[4..] {
            if let Some(rest) = token.strip_prefix("features=") {
                features.extend(parse_features(rest)?);
            } else {
                return Err(format!("bad workspace option {token}"));
            }
        }
        roots.push(Requirement {
            package: parts[2].to_string(),
            constraint: parts[3].to_string(),
            features,
        });
    }
    Ok(roots)
}

fn parse_registry(registry: &Path, package: &str) -> Result<Vec<VersionRecord>, String> {
    let path = registry.join(format!("{package}.pkg"));
    let text = fs::read_to_string(&path).map_err(|_| format!("missing package {package}"))?;
    let mut records: Vec<VersionRecord> = Vec::new();
    for (line_no, raw) in text.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<_> = line.split_whitespace().collect();
        match parts.first().copied() {
            Some("version") => {
                if parts.len() < 2 {
                    return Err(format!("bad version line {} in {package}", line_no + 1));
                }
                let mut yanked = false;
                for token in &parts[2..] {
                    if *token == "yanked=true" {
                        yanked = true;
                    } else {
                        return Err(format!("bad version option {token} in {package}"));
                    }
                }
                records.push(VersionRecord {
                    version: Version::parse(parts[1])?,
                    yanked,
                    deps: Vec::new(),
                    feature_deps: BTreeMap::new(),
                });
            }
            Some("dep") => {
                let dep = parse_dep_line(&parts, package, line_no + 1, 1)?;
                records.last_mut().ok_or_else(|| format!("dep before version in {package}"))?.deps.push(dep);
            }
            Some("feature") => {
                if parts.len() < 4 {
                    return Err(format!("bad feature line {} in {package}", line_no + 1));
                }
                let feature_name = parts[1].to_string();
                let dep = parse_dep_line(&parts, package, line_no + 1, 2)?;
                records
                    .last_mut()
                    .ok_or_else(|| format!("feature before version in {package}"))?
                    .feature_deps
                    .entry(feature_name)
                    .or_default()
                    .push(dep);
            }
            _ => return Err(format!("bad registry line {} in {package}", line_no + 1)),
        }
    }
    records.sort_by(|a, b| a.version.cmp(&b.version));
    Ok(records)
}

fn parse_dep_line(parts: &[&str], package: &str, line_no: usize, start: usize) -> Result<Requirement, String> {
    if parts.len() < start + 2 {
        return Err(format!("bad dependency line {line_no} in {package}"));
    }
    let mut features = BTreeSet::new();
    for token in &parts[start + 2..] {
        if let Some(rest) = token.strip_prefix("features=") {
            features.extend(parse_features(rest)?);
        } else {
            return Err(format!("bad dependency option {token} in {package}"));
        }
    }
    Ok(Requirement {
        package: parts[start].to_string(),
        constraint: parts[start + 1].to_string(),
        features,
    })
}

fn parse_features(s: &str) -> Result<BTreeSet<String>, String> {
    let mut out = BTreeSet::new();
    if s.is_empty() {
        return Ok(out);
    }
    for feature in s.split(',') {
        if feature.is_empty() {
            return Err("empty feature".to_string());
        }
        out.insert(feature.to_string());
    }
    Ok(out)
}

#[derive(Clone)]
struct Conflict {
    package: String,
    constraints: Vec<String>,
    reason: String,
}

fn resolve(opts: &Options, roots: Vec<Requirement>) -> Result<String, Vec<Conflict>> {
    let registry = Path::new(&opts.registry);
    let mut selected: BTreeMap<String, VersionRecord> = BTreeMap::new();
    let mut features: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut cache: BTreeMap<String, Vec<VersionRecord>> = BTreeMap::new();

    for _ in 0..200 {
        let mut constraints: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
        let mut next_features: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
        for root in roots.iter().cloned() {
            add_req(&mut constraints, &mut next_features, root);
        }

        let mut expanded = true;
        while expanded {
            expanded = false;
            let snapshot: Vec<(String, VersionRecord)> = selected
                .iter()
                .map(|(package, record)| (package.clone(), record.clone()))
                .collect();
            for (package, record) in snapshot {
                let empty = BTreeSet::new();
                let feature_set = next_features.get(&package).unwrap_or(&empty).clone();
                let mut active = record.deps.clone();
                for feature in &feature_set {
                    if let Some(reqs) = record.feature_deps.get(feature) {
                        active.extend(reqs.clone());
                    }
                }
                for req in active {
                    if add_req(&mut constraints, &mut next_features, req) {
                        expanded = true;
                    }
                }
            }
        }

        let mut next_selected: BTreeMap<String, VersionRecord> = BTreeMap::new();
        let mut conflicts = Vec::new();
        let packages: Vec<String> = constraints.keys().cloned().collect();
        for package in packages {
            let records = if let Some(records) = cache.get(&package) {
                records.clone()
            } else {
                match parse_registry(registry, &package) {
                    Ok(parsed) => {
                        cache.insert(package.clone(), parsed.clone());
                        parsed
                    }
                    Err(e) => {
                        conflicts.push(Conflict {
                            package: package.clone(),
                            constraints: sorted_constraints(&constraints, &package),
                            reason: e,
                        });
                        continue;
                    }
                }
            };
            match choose_version(&package, &records, &constraints) {
                Ok(chosen) => {
                    next_selected.insert(package, chosen);
                }
                Err(conflict) => {
                    conflicts.push(conflict);
                }
            }
        }

        if !conflicts.is_empty() {
            conflicts.sort_by(|a, b| a.package.cmp(&b.package));
            return Err(conflicts);
        }

        let same_versions = selected.len() == next_selected.len()
            && selected.iter().all(|(package, record)| {
                next_selected
                    .get(package)
                    .map(|next| next.version.raw.as_str())
                    == Some(record.version.raw.as_str())
            });
        if same_versions && features == next_features {
            return Ok(lock_json(&next_selected, &next_features));
        }
        selected = next_selected;
        features = next_features;
    }

    Err(vec![Conflict {
        package: "<resolver>".to_string(),
        constraints: vec![],
        reason: "resolution did not converge".to_string(),
    }])
}

fn add_req(
    constraints: &mut BTreeMap<String, BTreeSet<String>>,
    features: &mut BTreeMap<String, BTreeSet<String>>,
    req: Requirement,
) -> bool {
    let mut changed = false;
    changed |= constraints.entry(req.package.clone()).or_default().insert(req.constraint);
    let entry = features.entry(req.package).or_default();
    for feature in req.features {
        changed |= entry.insert(feature);
    }
    changed
}

fn choose_version(
    package: &str,
    records: &[VersionRecord],
    constraints: &BTreeMap<String, BTreeSet<String>>,
) -> Result<VersionRecord, Conflict> {
    for record in records.iter().rev() {
        if record.yanked {
            continue;
        }
        if constraints.get(package).unwrap().iter().all(|c| satisfies_all(&record.version, c)) {
            return Ok(record.clone());
        }
    }
    Err(Conflict {
        package: package.to_string(),
        constraints: sorted_constraints(constraints, package),
        reason: "no matching version".to_string(),
    })
}

fn sorted_constraints(constraints: &BTreeMap<String, BTreeSet<String>>, package: &str) -> Vec<String> {
    constraints.get(package).map(|s| s.iter().cloned().collect()).unwrap_or_default()
}

fn satisfies_all(version: &Version, constraint: &str) -> bool {
    constraint.split(',').all(|part| satisfies_one(version, part.trim()))
}

fn satisfies_one(version: &Version, part: &str) -> bool {
    let ops = [">=", "<=", ">", "<", "="];
    for op in ops {
        if let Some(rhs) = part.strip_prefix(op) {
            if let Ok(other) = Version::parse(rhs) {
                return match op {
                    ">=" => version >= &other,
                    "<=" => version <= &other,
                    ">" => version > &other,
                    "<" => version < &other,
                    "=" => version == &other,
                    _ => false,
                };
            }
        }
    }
    false
}

fn active_deps(record: &VersionRecord, package_features: &BTreeSet<String>, selected: &BTreeMap<String, VersionRecord>) -> Vec<(String, String)> {
    let mut names = BTreeSet::new();
    for dep in &record.deps {
        names.insert(dep.package.clone());
    }
    for feature in package_features {
        if let Some(reqs) = record.feature_deps.get(feature) {
            for dep in reqs {
                names.insert(dep.package.clone());
            }
        }
    }
    names
        .into_iter()
        .filter_map(|name| selected.get(&name).map(|r| (name, r.version.raw.clone())))
        .collect()
}

fn lock_json(selected: &BTreeMap<String, VersionRecord>, features: &BTreeMap<String, BTreeSet<String>>) -> String {
    let mut out = String::from("{\n  \"packages\": [\n");
    for (idx, (name, record)) in selected.iter().enumerate() {
        if idx > 0 {
            out.push_str(",\n");
        }
        let empty = BTreeSet::new();
        let feats = features.get(name).unwrap_or(&empty);
        let deps = active_deps(record, feats, selected);
        out.push_str("    {\n");
        out.push_str(&format!("      \"name\": \"{}\",\n", esc(name)));
        out.push_str(&format!("      \"version\": \"{}\",\n", esc(&record.version.raw)));
        out.push_str("      \"features\": [");
        for (fidx, feature) in feats.iter().enumerate() {
            if fidx > 0 {
                out.push_str(", ");
            }
            out.push_str(&format!("\"{}\"", esc(feature)));
        }
        out.push_str("],\n");
        out.push_str("      \"dependencies\": [");
        if !deps.is_empty() {
            out.push('\n');
            for (didx, (dep, version)) in deps.iter().enumerate() {
                if didx > 0 {
                    out.push_str(",\n");
                }
                out.push_str(&format!("        {{\"name\": \"{}\", \"version\": \"{}\"}}", esc(dep), esc(version)));
            }
            out.push_str("\n      ");
        }
        out.push_str("]\n");
        out.push_str("    }");
    }
    out.push_str("\n  ]\n}\n");
    out
}

fn conflict_report(conflicts: &[Conflict]) -> String {
    let mut sorted_conflicts = conflicts.to_vec();
    sorted_conflicts.sort_by(|a, b| a.package.cmp(&b.package));
    let mut out = String::from("{\n  \"conflicts\": [");
    if !sorted_conflicts.is_empty() {
        out.push('\n');
        for (cidx, conflict) in sorted_conflicts.iter().enumerate() {
            if cidx > 0 {
                out.push_str(",\n");
            }
            let mut sorted = conflict.constraints.clone();
            sorted.sort();
            out.push_str("    {\n");
            out.push_str(&format!("      \"package\": \"{}\",\n", esc(&conflict.package)));
            out.push_str("      \"constraints\": [");
            for (idx, constraint) in sorted.iter().enumerate() {
                if idx > 0 {
                    out.push_str(", ");
                }
                out.push_str(&format!("\"{}\"", esc(constraint)));
            }
            out.push_str("],\n");
            out.push_str(&format!("      \"reason\": \"{}\"\n", esc(&conflict.reason)));
            out.push_str("    }");
        }
        out.push('\n');
    }
    out.push_str("  ]\n}\n");
    out
}

fn write_output(path: &str, data: &str) -> Result<(), String> {
    let path = Path::new(path);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(path, data).map_err(|e| e.to_string())
}

fn esc(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}
RS

cargo build --locked --quiet
cargo build --locked
