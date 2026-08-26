use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

#[derive(Clone, Debug)]
struct MatrixRow {
    profile: String,
    channel: String,
    target: String,
    feature_set: String,
    max_runtime_kb: i64,
    allow_dev: bool,
    blocked_license: String,
}

#[derive(Clone, Debug)]
struct Component {
    name: String,
    version: String,
    license: String,
    kind: String,
    critical: bool,
    size_kb: i64,
    platforms: Vec<String>,
    owner: String,
}

#[derive(Clone, Debug)]
struct LockRow {
    profile: String,
    component: String,
    version: String,
    checksum: String,
    source: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Ord, PartialOrd)]
struct Edge {
    profile: String,
    parent: String,
    child: String,
    relation: String,
    scope: String,
    optional: bool,
}

#[derive(Clone, Debug)]
struct SelectedComponent {
    component: Component,
    lock: LockRow,
}

pub fn matrix_rows_nul(path: &Path) -> Result<Vec<u8>, String> {
    let mut out = Vec::new();
    for row in load_matrix(path)? {
        let fields = [
            row.profile,
            row.channel,
            row.target,
            row.feature_set,
            row.max_runtime_kb.to_string(),
            bool_word(row.allow_dev).to_string(),
            row.blocked_license,
        ];
        for field in fields {
            out.extend_from_slice(field.as_bytes());
            out.push(0);
        }
    }
    Ok(out)
}

pub fn license_lines(path: &Path) -> Result<Vec<u8>, String> {
    let licenses: BTreeSet<String> = load_components(path)?
        .into_values()
        .map(|component| component.license)
        .collect();
    let mut out = Vec::new();
    for license in licenses {
        out.extend_from_slice(license.as_bytes());
        out.push(b'\n');
    }
    Ok(out)
}

pub fn audit_to_file(
    profile: &str,
    matrix: &Path,
    components: &Path,
    locks: &Path,
    edges: &Path,
    out: &Path,
) -> Result<(), String> {
    let json = audit_to_json(profile, matrix, components, locks, edges)?;
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("failed to create {}: {err}", parent.display()))?;
    }
    fs::write(out, format!("{json}\n"))
        .map_err(|err| format!("failed to write {}: {err}", out.display()))
}

pub fn audit_to_json(
    profile: &str,
    matrix_path: &Path,
    components_path: &Path,
    locks_path: &Path,
    edges_path: &Path,
) -> Result<String, String> {
    let matrix = load_matrix(matrix_path)?;
    let row = matrix
        .into_iter()
        .find(|item| item.profile == profile)
        .ok_or_else(|| format!("unknown profile {profile}"))?;
    let components = load_components(components_path)?;
    let locks = load_locks(locks_path)?;
    let edges = load_edges(edges_path)?;
    let profile_locks: Vec<LockRow> = locks
        .into_iter()
        .filter(|lock| lock.profile == profile)
        .collect();
    if profile_locks.is_empty() {
        return Err(format!("no lock rows for profile {profile}"));
    }

    let mut warnings = Vec::new();
    let mut selected = BTreeMap::new();
    for lock in profile_locks {
        match components.get(&lock.component) {
            Some(component) => {
                selected.insert(
                    lock.component.clone(),
                    SelectedComponent {
                        component: component.clone(),
                        lock,
                    },
                );
            }
            None => warnings.push(format!("missing_component:{}", lock.component)),
        }
    }

    let names: BTreeSet<String> = selected.keys().cloned().collect();
    let mut active_edges = Vec::new();
    for edge in edges {
        if edge.profile != "*" && edge.profile != profile {
            continue;
        }
        if !scope_active(&edge.scope, &row) {
            continue;
        }
        if names.contains(&edge.parent) && names.contains(&edge.child) {
            active_edges.push(edge);
        } else if !edge.optional && names.contains(&edge.parent) && !names.contains(&edge.child) {
            warnings.push(format!(
                "missing_required_edge:{}->{}",
                edge.parent, edge.child
            ));
        }
    }

    let order = topo_order(&names, &active_edges, &mut warnings);
    let mut ordered = Vec::new();
    for name in order {
        if let Some(item) = selected.get(&name) {
            ordered.push(item.clone());
        }
    }

    let mut runtime_kb = 0_i64;
    let mut critical_count = 0_i64;
    let mut dev_count = 0_i64;
    let mut licenses = BTreeSet::new();
    let mut owners = BTreeSet::new();
    for item in &ordered {
        let component = &item.component;
        licenses.insert(component.license.clone());
        owners.insert(component.owner.clone());
        if component.critical {
            critical_count += 1;
        }
        if component.kind == "dev" {
            dev_count += 1;
            if !row.allow_dev {
                warnings.push(format!("dev_dependency:{}", component.name));
            }
        }
        if component.kind != "doc" {
            runtime_kb += component.size_kb;
        }
        if component.license == row.blocked_license {
            warnings.push(format!(
                "blocked_license:{}:{}",
                component.name, component.license
            ));
        }
        if component.version != item.lock.version {
            warnings.push(format!(
                "version_mismatch:{}:{}:{}",
                component.name, item.lock.version, component.version
            ));
        }
        if !component
            .platforms
            .iter()
            .any(|platform| platform == &row.target)
        {
            warnings.push(format!("platform:{}:{}", component.name, row.target));
        }
    }
    if runtime_kb > row.max_runtime_kb {
        warnings.push(format!("runtime_size:{runtime_kb}:{}", row.max_runtime_kb));
    }
    warnings.sort();
    warnings.dedup();

    let mut edge_strings: Vec<String> = active_edges
        .iter()
        .map(|edge| format!("{}->{}:{}", edge.parent, edge.child, edge.relation))
        .collect();
    edge_strings.sort();
    let blocked_ok = !warnings
        .iter()
        .any(|item| item.starts_with("blocked_license:"));
    let platform_ok = !warnings.iter().any(|item| item.starts_with("platform:"));
    let dev_ok = !warnings
        .iter()
        .any(|item| item.starts_with("dev_dependency:"));
    let runtime_ok = runtime_kb <= row.max_runtime_kb;
    let locked_ok = !warnings.iter().any(|item| {
        item.starts_with("version_mismatch:")
            || item.starts_with("missing_component:")
            || item.starts_with("missing_required_edge:")
    });
    let policy_checks = vec![
        format!("blocked_license:{}", ok_word(blocked_ok)),
        format!("dev_policy:{}", ok_word(dev_ok)),
        format!("locked_versions:{}", ok_word(locked_ok)),
        format!("platforms:{}", ok_word(platform_ok)),
        format!(
            "runtime_size:{}:{runtime_kb}/{}",
            ok_word(runtime_ok),
            row.max_runtime_kb
        ),
    ];
    let license_count = licenses.len();
    let risk_score = warnings.len() as i64 * 31
        + dev_count * 3
        + critical_count * 5
        + edge_strings.len() as i64 * 2
        + if runtime_ok { 0 } else { 13 };

    let mut out = String::new();
    out.push_str("{\n");
    push_str(&mut out, "profile", &row.profile, true);
    push_str(&mut out, "target", &row.target, true);
    push_str(&mut out, "channel", &row.channel, true);
    push_str(&mut out, "feature_set", &row.feature_set, true);
    push_num(&mut out, "max_runtime_kb", row.max_runtime_kb, true);
    push_bool(&mut out, "allow_dev", row.allow_dev, true);
    out.push_str("  \"components\": [\n");
    for (index, item) in ordered.iter().enumerate() {
        let component = &item.component;
        out.push_str("    {");
        out.push_str(&format!("\"name\":\"{}\"", esc(&component.name)));
        out.push_str(&format!(",\"version\":\"{}\"", esc(&component.version)));
        out.push_str(&format!(",\"kind\":\"{}\"", esc(&component.kind)));
        out.push_str(&format!(",\"license\":\"{}\"", esc(&component.license)));
        out.push_str(&format!(",\"critical\":{}", bool_word(component.critical)));
        out.push_str(&format!(",\"size_kb\":{}", component.size_kb));
        out.push_str(&format!(",\"checksum\":\"{}\"", esc(&item.lock.checksum)));
        out.push_str(&format!(",\"source\":\"{}\"", esc(&item.lock.source)));
        out.push_str(",\"direct\":true}");
        if index + 1 != ordered.len() {
            out.push(',');
        }
        out.push('\n');
    }
    out.push_str("  ],\n");
    push_array(&mut out, "dependency_edges", &edge_strings, true);
    push_array(
        &mut out,
        "license_summary",
        &licenses.into_iter().collect::<Vec<_>>(),
        true,
    );
    push_array(
        &mut out,
        "owners",
        &owners.into_iter().collect::<Vec<_>>(),
        true,
    );
    push_array(&mut out, "policy_checks", &policy_checks, true);
    push_array(&mut out, "warnings", &warnings, true);
    out.push_str("  \"totals\": {");
    out.push_str(&format!("\"component_count\":{}", ordered.len()));
    out.push_str(&format!(",\"direct_lock_count\":{}", selected.len()));
    out.push_str(&format!(",\"runtime_kb\":{}", runtime_kb));
    out.push_str(&format!(",\"critical_count\":{}", critical_count));
    out.push_str(&format!(",\"license_count\":{}", license_count));
    out.push_str(&format!(",\"dev_component_count\":{}", dev_count));
    out.push_str(&format!(",\"edge_count\":{}", edge_strings.len()));
    out.push_str(&format!(
        ",\"policy_pass\":{}",
        bool_word(warnings.is_empty())
    ));
    out.push_str(&format!(",\"risk_score\":{}", risk_score));
    out.push_str("}\n}");
    Ok(out)
}

fn topo_order(names: &BTreeSet<String>, edges: &[Edge], warnings: &mut Vec<String>) -> Vec<String> {
    let mut graph: BTreeMap<String, BTreeSet<String>> = names
        .iter()
        .map(|name| (name.clone(), BTreeSet::new()))
        .collect();
    let mut reverse = graph.clone();
    for edge in edges {
        graph
            .entry(edge.parent.clone())
            .or_default()
            .insert(edge.child.clone());
        reverse
            .entry(edge.child.clone())
            .or_default()
            .insert(edge.parent.clone());
    }

    let mut finish_order = Vec::new();
    let mut seen = BTreeSet::new();
    for name in names {
        if seen.contains(name) {
            continue;
        }
        let mut stack = vec![(name.clone(), false)];
        while let Some((node, expanded)) = stack.pop() {
            if expanded {
                finish_order.push(node);
                continue;
            }
            if !seen.insert(node.clone()) {
                continue;
            }
            stack.push((node.clone(), true));
            if let Some(children) = graph.get(&node) {
                for child in children.iter().rev() {
                    if !seen.contains(child) {
                        stack.push((child.clone(), false));
                    }
                }
            }
        }
    }
    seen.clear();
    let mut components: Vec<Vec<String>> = Vec::new();
    for name in finish_order.into_iter().rev() {
        if seen.contains(&name) {
            continue;
        }
        let mut component = Vec::new();
        let mut stack = vec![name];
        while let Some(node) = stack.pop() {
            if !seen.insert(node.clone()) {
                continue;
            }
            component.push(node.clone());
            if let Some(parents) = reverse.get(&node) {
                stack.extend(parents.iter().rev().cloned());
            }
        }
        component.sort();
        components.push(component);
    }
    components.sort_by(|left, right| left[0].cmp(&right[0]));

    let mut component_of = BTreeMap::new();
    for (index, component) in components.iter().enumerate() {
        for name in component {
            component_of.insert(name.clone(), index);
        }
        let self_loop = component.len() == 1
            && graph
                .get(&component[0])
                .is_some_and(|children| children.contains(&component[0]));
        if component.len() > 1 || self_loop {
            warnings.push(format!("dependency_cycle:{}", component.join("|")));
        }
    }

    let mut dag: Vec<BTreeSet<usize>> = vec![BTreeSet::new(); components.len()];
    let mut indegree = vec![0_usize; components.len()];
    for (parent, children) in &graph {
        let from = component_of[parent];
        for child in children {
            let to = component_of[child];
            if from != to && dag[from].insert(to) {
                indegree[to] += 1;
            }
        }
    }
    let mut emitted = BTreeSet::new();
    let mut out = Vec::new();
    while emitted.len() < components.len() {
        let next = (0..components.len())
            .filter(|index| !emitted.contains(index) && indegree[*index] == 0)
            .min_by(|left, right| components[*left][0].cmp(&components[*right][0]))
            .expect("condensation graph is acyclic");
        emitted.insert(next);
        out.extend(components[next].iter().cloned());
        for child in &dag[next] {
            indegree[*child] -= 1;
        }
    }
    out
}

fn scope_active(scope: &str, row: &MatrixRow) -> bool {
    if matches!(scope, "" | "all" | "runtime" | "data" | "doc" | "dev") {
        return true;
    }
    let features: BTreeSet<&str> = row
        .feature_set
        .split('+')
        .filter(|value| !value.is_empty())
        .collect();
    if let Some(expression) = scope.strip_prefix("cfg:") {
        let chars: Vec<char> = expression.chars().collect();
        let mut index = 0;
        return parse_scope_expression(&chars, &mut index, &features, row) == Some(true)
            && index == chars.len();
    }
    scope.split('&').all(|clause| {
        let (negated, atom) = clause
            .strip_prefix('!')
            .map_or((false, clause), |rest| (true, rest));
        let value = scope_atom(atom, &features, row).unwrap_or(false);
        value != negated
    })
}

fn scope_atom(atom: &str, features: &BTreeSet<&str>, row: &MatrixRow) -> Option<bool> {
    if let Some(feature) = atom.strip_prefix("feature:") {
        Some(features.contains(feature))
    } else if let Some(target) = atom.strip_prefix("target:") {
        Some(row.target == target)
    } else if let Some(channel) = atom.strip_prefix("channel:") {
        Some(row.channel == channel)
    } else {
        None
    }
}

fn parse_scope_expression(
    chars: &[char],
    index: &mut usize,
    features: &BTreeSet<&str>,
    row: &MatrixRow,
) -> Option<bool> {
    fn starts(chars: &[char], index: usize, text: &str) -> bool {
        let length = text.chars().count();
        chars
            .get(index..index + length)
            .map(|slice| slice.iter().collect::<String>() == text)
            .unwrap_or(false)
    }
    for (operator, all) in [("all(", true), ("any(", false)] {
        if starts(chars, *index, operator) {
            *index += operator.len();
            let mut values = Vec::new();
            loop {
                values.push(parse_scope_expression(chars, index, features, row)?);
                match chars.get(*index) {
                    Some(',') => *index += 1,
                    Some(')') => {
                        *index += 1;
                        break;
                    }
                    _ => return None,
                }
            }
            return Some(if all {
                values.into_iter().all(|value| value)
            } else {
                values.into_iter().any(|value| value)
            });
        }
    }
    if starts(chars, *index, "not(") {
        *index += 4;
        let value = parse_scope_expression(chars, index, features, row)?;
        if chars.get(*index) != Some(&')') {
            return None;
        }
        *index += 1;
        return Some(!value);
    }
    let start = *index;
    while *index < chars.len() && chars[*index] != ',' && chars[*index] != ')' {
        *index += 1;
    }
    if start == *index {
        return None;
    }
    let atom: String = chars[start..*index].iter().collect();
    scope_atom(&atom, features, row)
}

fn load_matrix(path: &Path) -> Result<Vec<MatrixRow>, String> {
    let mut out = Vec::new();
    for row in read_csv(path)? {
        out.push(MatrixRow {
            profile: field(&row, "profile")?,
            channel: field(&row, "channel")?,
            target: field(&row, "target")?,
            feature_set: field(&row, "feature_set")?,
            max_runtime_kb: field(&row, "max_runtime_kb")?
                .parse()
                .map_err(|err| format!("invalid max_runtime_kb: {err}"))?,
            allow_dev: matches!(field(&row, "allow_dev")?.as_str(), "true" | "yes" | "1"),
            blocked_license: field(&row, "blocked_license")?,
        });
    }
    Ok(out)
}

fn load_components(path: &Path) -> Result<BTreeMap<String, Component>, String> {
    let mut out = BTreeMap::new();
    for row in read_csv(path)? {
        let component = Component {
            name: field(&row, "component")?,
            version: field(&row, "version")?,
            license: field(&row, "license")?,
            kind: field(&row, "kind")?,
            critical: matches!(
                field(&row, "critical")?.to_ascii_lowercase().as_str(),
                "yes" | "true" | "1"
            ),
            size_kb: field(&row, "size_kb")?
                .parse()
                .map_err(|err| format!("invalid size_kb: {err}"))?,
            platforms: field(&row, "platforms")?
                .split('|')
                .map(|item| item.to_string())
                .collect(),
            owner: field(&row, "owner")?,
        };
        out.insert(component.name.clone(), component);
    }
    Ok(out)
}

fn load_locks(path: &Path) -> Result<Vec<LockRow>, String> {
    let mut out = Vec::new();
    for row in read_csv(path)? {
        out.push(LockRow {
            profile: field(&row, "profile")?,
            component: field(&row, "component")?,
            version: field(&row, "version")?,
            checksum: field(&row, "checksum")?,
            source: field(&row, "source")?,
        });
    }
    Ok(out)
}

fn load_edges(path: &Path) -> Result<Vec<Edge>, String> {
    let mut out = Vec::new();
    for row in read_csv(path)? {
        out.push(Edge {
            profile: field(&row, "profile")?,
            parent: field(&row, "parent")?,
            child: field(&row, "child")?,
            relation: field(&row, "relation")?,
            scope: field(&row, "scope")?,
            optional: matches!(field(&row, "optional")?.as_str(), "yes" | "true" | "1"),
        });
    }
    Ok(out)
}

fn read_csv(path: &Path) -> Result<Vec<BTreeMap<String, String>>, String> {
    let text = fs::read_to_string(path)
        .map_err(|err| format!("failed to read {}: {err}", path.display()))?;
    let mut records = parse_csv(&text)
        .map_err(|error| format!("{}: {error}", path.display()))?
        .into_iter()
        .filter(|row| !(row.len() == 1 && row[0].is_empty()));
    let headers = records
        .next()
        .ok_or_else(|| format!("{} is empty", path.display()))?;
    let mut out = Vec::new();
    for (index, values) in records.enumerate() {
        if values.len() != headers.len() {
            return Err(format!(
                "{} line {} has {} fields, expected {}",
                path.display(),
                index + 2,
                values.len(),
                headers.len()
            ));
        }
        out.push(headers.iter().cloned().zip(values).collect());
    }
    Ok(out)
}

fn parse_csv(text: &str) -> Result<Vec<Vec<String>>, String> {
    let chars: Vec<char> = text.chars().collect();
    let mut records = Vec::new();
    let mut record = Vec::new();
    let mut field = String::new();
    let mut quoted = false;
    let mut index = 0;
    while index < chars.len() {
        let ch = chars[index];
        if quoted {
            if ch == '"' {
                if index + 1 < chars.len() && chars[index + 1] == '"' {
                    field.push('"');
                    index += 1;
                } else {
                    quoted = false;
                }
            } else {
                field.push(ch);
            }
        } else {
            match ch {
                '"' if field.is_empty() => quoted = true,
                ',' => record.push(std::mem::take(&mut field)),
                '\n' => {
                    record.push(std::mem::take(&mut field));
                    records.push(std::mem::take(&mut record));
                }
                '\r' => {
                    if index + 1 < chars.len() && chars[index + 1] == '\n' {
                        index += 1;
                    }
                    record.push(std::mem::take(&mut field));
                    records.push(std::mem::take(&mut record));
                }
                _ => field.push(ch),
            }
        }
        index += 1;
    }
    if quoted {
        return Err("unterminated quoted field".to_string());
    }
    if !field.is_empty() || !record.is_empty() {
        record.push(field);
        records.push(record);
    }
    Ok(records)
}

fn field(row: &BTreeMap<String, String>, key: &str) -> Result<String, String> {
    row.get(key)
        .cloned()
        .ok_or_else(|| format!("missing field {key}"))
}

fn ok_word(value: bool) -> &'static str {
    if value {
        "ok"
    } else {
        "fail"
    }
}
fn bool_word(value: bool) -> &'static str {
    if value {
        "true"
    } else {
        "false"
    }
}
fn push_str(out: &mut String, key: &str, value: &str, comma: bool) {
    out.push_str(&format!(
        "  \"{}\": \"{}\"{}\n",
        key,
        esc(value),
        if comma { "," } else { "" }
    ));
}
fn push_num(out: &mut String, key: &str, value: i64, comma: bool) {
    out.push_str(&format!(
        "  \"{}\": {}{}\n",
        key,
        value,
        if comma { "," } else { "" }
    ));
}
fn push_bool(out: &mut String, key: &str, value: bool, comma: bool) {
    out.push_str(&format!(
        "  \"{}\": {}{}\n",
        key,
        bool_word(value),
        if comma { "," } else { "" }
    ));
}
fn push_array(out: &mut String, key: &str, values: &[String], comma: bool) {
    out.push_str(&format!(
        "  \"{}\": {}{}\n",
        key,
        json_array(values),
        if comma { "," } else { "" }
    ));
}
fn json_array(values: &[String]) -> String {
    let mut out = String::from("[");
    for (index, value) in values.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        out.push('"');
        out.push_str(&esc(value));
        out.push('"');
    }
    out.push(']');
    out
}
fn esc(value: &str) -> String {
    let mut out = String::new();
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            ch if ch < ' ' => out.push_str(&format!("\\u{:04x}", ch as u32)),
            ch => out.push(ch),
        }
    }
    out
}
