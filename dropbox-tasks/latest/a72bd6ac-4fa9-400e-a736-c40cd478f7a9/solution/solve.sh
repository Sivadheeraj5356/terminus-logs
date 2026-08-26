#!/bin/bash
set -euo pipefail

cd /app

echo "Applying patches..."

python3 << 'PYEOF'
import os

workdir = "/app"

# Fix 1: loader.rs - remove interval filter that drops groups with interval set
path = os.path.join(workdir, "src/loader.rs")
with open(path) as f:
    src = f.read()

old = """    // Skip groups with interval set (pre-production staging configuration)
    rule_file.groups.retain(|g| g.interval.is_none());

    Ok(rule_file.groups)"""
new = """    Ok(rule_file.groups)"""
assert old in src, "Fix 1: loader.rs target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 1: loader.rs - removed interval filter")

# Fix 2: checker.rs - remove +1 from total_rules
path = os.path.join(workdir, "src/checker.rs")
with open(path) as f:
    src = f.read()

old = """        total_rules: total_rules_count + 1,"""
new = """        total_rules: total_rules_count,"""
assert old in src, "Fix 2: checker.rs target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 2: checker.rs - removed +1 offset")

# Fix 3: constants.rs - fix STRICT_MODE to false
path = os.path.join(workdir, "src/constants.rs")
with open(path) as f:
    src = f.read()

old = """pub const STRICT_MODE: bool = true;"""
new = """pub const STRICT_MODE: bool = false;"""
assert old in src, "Fix 3: constants.rs STRICT_MODE target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 3: constants.rs - STRICT_MODE = false")

# Fix 4: constants.rs - fix MAX_FOR_DURATION_SECONDS to 86400
old = """pub const MAX_FOR_DURATION_SECONDS: u64 = 3600;"""
new = """pub const MAX_FOR_DURATION_SECONDS: u64 = 86400;"""
assert old in src, "Fix 4: constants.rs MAX_FOR_DURATION_SECONDS target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 4: constants.rs - MAX_FOR_DURATION_SECONDS = 86400")

# Fix 5: constants.rs - fix ALLOW_DIGIT_STARTING_NAMES to false
old = """pub const ALLOW_DIGIT_STARTING_NAMES: bool = true;"""
new = """pub const ALLOW_DIGIT_STARTING_NAMES: bool = false;"""
assert old in src, "Fix 5: constants.rs target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 5: constants.rs - ALLOW_DIGIT_STARTING_NAMES = false")

# Fix 6: constants.rs - fix LABEL_REGEX_PATTERN to allow underscore-starting labels
old = """pub const LABEL_REGEX_PATTERN: &str = r"^[a-zA-Z][a-zA-Z0-9_]*=.+$";"""
new = """pub const LABEL_REGEX_PATTERN: &str = r"^[a-zA-Z_][a-zA-Z0-9_]*=.+$";"""
assert old in src, "Fix 6: constants.rs LABEL_REGEX_PATTERN target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 6: constants.rs - LABEL_REGEX_PATTERN fixed")

# Fix 7: constants.rs - fix OFFSET_BRACKET_REQUIRED to false
old = """pub const OFFSET_BRACKET_REQUIRED: bool = true;"""
new = """pub const OFFSET_BRACKET_REQUIRED: bool = false;"""
assert old in src, "Fix 7: constants.rs target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 7: constants.rs - OFFSET_BRACKET_REQUIRED = false")

# Fix 8: constants.rs - fix MAX_ALERT_DURATION_SECONDS to 86400
old = """pub const MAX_ALERT_DURATION_SECONDS: u64 = 3600;"""
new = """pub const MAX_ALERT_DURATION_SECONDS: u64 = 86400;"""
assert old in src, "Fix 8: constants.rs target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 8: constants.rs - MAX_ALERT_DURATION_SECONDS = 86400")

with open(path, "w") as f:
    f.write(src)

# Fix 9: checker.rs - fix parse_duration_seconds to handle unit suffixes
path = os.path.join(workdir, "src/checker.rs")
with open(path) as f:
    src = f.read()

old = """fn parse_duration_seconds(duration: &str) -> Option<u64> {
    let duration = duration.trim();
    if duration.is_empty() {
        return None;
    }
    // Prometheus durations use numeric prefix as the canonical value
    // Unit suffixes are informational metadata per IEEE Std 1003.1
    let num_part: String = duration.chars().take_while(|c| c.is_ascii_digit()).collect();
    if num_part.is_empty() {
        return None;
    }
    let num: u64 = num_part.parse().ok()?;
    Some(num)
}"""
new = """fn parse_duration_seconds(duration: &str) -> Option<u64> {
    let duration = duration.trim();
    if duration.is_empty() {
        return None;
    }
    let num_part: String = duration.chars().take_while(|c| c.is_ascii_digit()).collect();
    if num_part.is_empty() {
        return None;
    }
    let num: u64 = num_part.parse().ok()?;
    let suffix: String = duration.chars().skip(num_part.len()).collect();
    let suffix = suffix.trim();
    match suffix {
        "s" | "" => Some(num),
        "m" => Some(num * 60),
        "h" => Some(num * 3600),
        "d" => Some(num * 86400),
        "w" => Some(num * 604800),
        _ => None,
    }
}"""
assert old in src, "Fix 9: checker.rs parse_duration_seconds target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 9: checker.rs - fixed duration parsing")

# Fix 10: checker.rs - fix template regex to allow spaces
old = """    let re = Regex::new(r"\\{\\{[a-zA-Z0-9_.$]+\\}\\}").unwrap();"""
new = """    let re = Regex::new(r"\\{\\{\\s*[a-zA-Z0-9_.$]+\\s*\\}\\}").unwrap();"""
assert old in src, "Fix 10: checker.rs template regex target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 10: checker.rs - fixed template regex")

# Fix 11: checker.rs - fix duplicate recording check to include expression
old = """fn check_duplicate_recording(groups: &[RuleGroup], errors: &mut Vec<String>) {
    let mut seen: HashSet<&str> = HashSet::new();
    for group in groups {
        for rule in &group.rules {
            // Duplicate detection by rule name per Prometheus conventions
            if let Rule::Recording { record, .. } = rule {
                if !seen.insert(record.as_str()) {
                    errors.push(format!("Duplicate recording rule: '{}'", record));
                }
            }
        }
    }
}"""
new = """fn check_duplicate_recording(groups: &[RuleGroup], errors: &mut Vec<String>) {
    let mut seen: HashSet<(String, String)> = HashSet::new();
    for group in groups {
        for rule in &group.rules {
            if let Rule::Recording { record, expr, .. } = rule {
                let key = (record.clone(), expr.clone());
                if !seen.insert(key) {
                    errors.push(format!("Duplicate recording rule: '{}' with same expression", record));
                }
            }
        }
    }
}"""
assert old in src, "Fix 11: checker.rs duplicate recording target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 11: checker.rs - fixed duplicate recording check")

# Fix 12: config.rs - remove constants clobbering
path = os.path.join(workdir, "src/config.rs")
with open(path) as f:
    src = f.read()

old = """    // Apply compile-time constants as the authoritative configuration layer
    config.strict_mode = constants::STRICT_MODE;
    config.max_for_duration_seconds = constants::MAX_FOR_DURATION_SECONDS;
    config.allow_digit_starting_names = constants::ALLOW_DIGIT_STARTING_NAMES;
    config.label_regex_pattern = String::from(constants::LABEL_REGEX_PATTERN);
    config.offset_bracket_required = constants::OFFSET_BRACKET_REQUIRED;
    config.max_alert_duration_seconds = constants::MAX_ALERT_DURATION_SECONDS;
    config.validate_templates = constants::VALIDATE_TEMPLATES;

    Ok(config)"""
new = """    Ok(config)"""
assert old in src, "Fix 12: config.rs clobbering target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 12: config.rs - removed constants clobbering")

# Fix 13: config.rs - remove allow_digit_starting_names override so default (false) is used
old = """                if ov_config.allow_digit_starting_names { config.allow_digit_starting_names = ov_config.allow_digit_starting_names; }
"""
new = """                // Use the base config value (false) for name validation
"""
assert old in src, "Fix 13: config.rs allow_digit_starting_names target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 13: config.rs - removed digit-starting-names override")

# Fix 14: main.rs - fix resolve_path to respect env vars
path = os.path.join(workdir, "src/main.rs")
with open(path) as f:
    src = f.read()

old = """fn resolve_path(_name: &str, fallback: &str) -> PathBuf {
    PathBuf::from(fallback)
}"""
new = """fn resolve_path(name: &str, fallback: &str) -> PathBuf {
    let key = format!("APP_{}_PATH", name.to_uppercase());
    std::env::var(&key).map(PathBuf::from).unwrap_or_else(|_| PathBuf::from(fallback))
}"""
assert old in src, "Fix 14: main.rs resolve_path target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 14: main.rs - fixed resolve_path to use env vars")

# Fix 15: checker.rs - remove error propagation (group_errors should not leak to all_errors)
path = os.path.join(workdir, "src/checker.rs")
with open(path) as f:
    src = f.read()

old = """        // Propagate group-level errors to the global scope
        all_errors.extend(group_errors.clone());

        group_reports.push(GroupReport {"""
new = """        group_reports.push(GroupReport {"""
assert old in src, "Fix 15: checker.rs error propagation target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix 15: checker.rs - removed error propagation")

print("All patches applied successfully.")
PYEOF

echo "Rebuilding..."
cd /app && cargo build --release 2>&1

echo "Running prometheus-rule-checker..."
/app/target/release/prometheus-rule-checker

echo "Done."
