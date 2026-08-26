#!/bin/bash
set -euo pipefail

TASK_DIR="${TASK_DIR:-/app/task_file}"
cat > "$TASK_DIR/src/lib.rs" <<'RS'
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, PartialEq)]
pub struct GrubRollout {
    pub files: Vec<ConfigFile>,
    pub hosts: Vec<HostState>,
    pub policy: RolloutPolicy,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ConfigFile {
    pub path: String,
    pub content: String,
}

#[derive(Clone, Debug, PartialEq)]
pub struct HostState {
    pub hostname: String,
    pub bootloader: String,
    pub arch: String,
    pub secure_boot: bool,
    pub lockdown: bool,
    pub tpm2: bool,
    pub root_fs: String,
    pub encrypted_root: bool,
    pub kernel_version: String,
    pub cmdline_runtime: String,
    pub modules: Vec<ModuleState>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ModuleState {
    pub name: String,
    pub loaded: bool,
    pub builtin: bool,
    pub signed: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct RolloutPolicy {
    pub min_kernel_version: String,
    pub require_secure_boot: bool,
    pub require_lockdown: bool,
    pub require_iommu: bool,
    pub forbidden_params: Vec<String>,
    pub required_params: Vec<String>,
    pub allowed_debug_params: Vec<String>,
    pub required_luks_params: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AuditReport {
    pub effective: EffectiveGrubConfig,
    pub hosts: Vec<HostAudit>,
    pub global_findings: Vec<String>,
    pub finding_count_by_code: BTreeMap<String, usize>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct EffectiveGrubConfig {
    pub source_order: Vec<String>,
    pub cmdline_linux: Vec<String>,
    pub cmdline_linux_default: Vec<String>,
    pub disable_os_prober: Option<bool>,
    pub distributor: Option<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct HostAudit {
    pub hostname: String,
    pub blockers: Vec<String>,
    pub warnings: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct RolloutSummary {
    pub host_count: usize,
    pub blocked_hosts: Vec<String>,
    pub warning_hosts: Vec<String>,
    pub clean_hosts: Vec<String>,
    pub blocker_count_by_host: BTreeMap<String, usize>,
    pub warning_count_by_host: BTreeMap<String, usize>,
    pub top_finding_codes: Vec<(String, usize)>,
    pub required_runtime_coverage: BTreeMap<String, usize>,
    pub effective_param_keys: Vec<String>,
    pub rollout_ready: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct RemediationAction {
    pub priority: u8,
    pub code: String,
    pub detail: String,
    pub targets: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct RolloutWave {
    pub name: String,
    pub hosts: Vec<String>,
    pub risk_score: usize,
    pub required_actions: Vec<String>,
}

#[derive(Default)]
struct ParsedConfig {
    effective: EffectiveGrubConfig,
    bad_bools: Vec<String>,
}

impl Default for EffectiveGrubConfig {
    fn default() -> Self {
        Self {
            source_order: Vec::new(),
            cmdline_linux: Vec::new(),
            cmdline_linux_default: Vec::new(),
            disable_os_prober: None,
            distributor: None,
        }
    }
}

impl GrubRollout {
    pub fn audit(&self) -> AuditReport {
        let parsed = parse_config(&self.files);
        let effective_tokens = all_effective_tokens(&parsed.effective);
        let effective_keys = keys_for(&effective_tokens);
        let effective_key_set: BTreeSet<String> = effective_keys.iter().cloned().collect();
        let mut global_findings = parsed.bad_bools.clone();

        if parsed.effective.disable_os_prober == Some(false) {
            global_findings.push("os-prober-enabled".to_string());
        }

        for key in &self.policy.forbidden_params {
            if effective_key_set.contains(key) {
                global_findings.push(format!("forbidden-param:{key}"));
            }
        }
        for key in &self.policy.required_params {
            if !effective_key_set.contains(key) {
                global_findings.push(format!("missing-required-param:{key}"));
            }
        }
        for key in &self.policy.required_luks_params {
            if !effective_key_set.contains(key) {
                global_findings.push(format!("missing-luks-param:{key}"));
            }
        }

        let mut counts: BTreeMap<String, usize> = BTreeMap::new();
        for key in &effective_keys {
            *counts.entry(key.clone()).or_insert(0) += 1;
        }
        for (key, count) in counts {
            if count > 1 && key != "rd.luks.uuid" {
                global_findings.push(format!("duplicate-param:{key}"));
            }
        }

        for (left, right) in [
            ("quiet", "debug"),
            ("nomodeset", "i915.modeset"),
            ("intel_iommu", "amd_iommu"),
            ("systemd.unified_cgroup_hierarchy", "cgroup_no_v1"),
        ] {
            if effective_key_set.contains(left) && effective_key_set.contains(right) {
                global_findings.push(format!("conflict-param:{left}:{right}"));
            }
        }
        for token in &effective_tokens {
            let key = key_of(token);
            if is_iommu_key(&key) {
                if let Some(value) = value_of(token) {
                    if is_weak_iommu_value(&value) {
                        global_findings.push(format!("weak-iommu-setting:{key}:{value}"));
                    }
                }
            }
        }
        global_findings.sort();

        let mut hosts = Vec::new();
        for host in &self.hosts {
            hosts.push(audit_host(host, &self.policy, &effective_tokens, &effective_keys));
        }

        let mut finding_count_by_code = BTreeMap::new();
        for finding in &global_findings {
            add_count(&mut finding_count_by_code, finding);
        }
        for host in &hosts {
            for finding in &host.blockers {
                add_count(&mut finding_count_by_code, finding);
            }
            for finding in &host.warnings {
                add_count(&mut finding_count_by_code, finding);
            }
        }

        AuditReport {
            effective: parsed.effective,
            hosts,
            global_findings,
            finding_count_by_code,
        }
    }
}

impl AuditReport {
    pub fn rollout_summary(&self) -> RolloutSummary {
        let mut blocked_hosts = Vec::new();
        let mut warning_hosts = Vec::new();
        let mut clean_hosts = Vec::new();
        let mut blocker_count_by_host = BTreeMap::new();
        let mut warning_count_by_host = BTreeMap::new();

        for host in &self.hosts {
            if !host.blockers.is_empty() {
                blocked_hosts.push(host.hostname.clone());
                blocker_count_by_host.insert(host.hostname.clone(), host.blockers.len());
            } else if !host.warnings.is_empty() {
                warning_hosts.push(host.hostname.clone());
            } else {
                clean_hosts.push(host.hostname.clone());
            }
            if !host.warnings.is_empty() {
                warning_count_by_host.insert(host.hostname.clone(), host.warnings.len());
            }
        }

        let mut top_finding_codes: Vec<(String, usize)> = self
            .finding_count_by_code
            .iter()
            .map(|(code, count)| (code.clone(), *count))
            .collect();
        top_finding_codes.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
        top_finding_codes.truncate(5);

        let effective_tokens = all_effective_tokens(&self.effective);
        let mut effective_param_keys = Vec::new();
        let mut seen = BTreeSet::new();
        for token in &effective_tokens {
            let key = key_of(token);
            if seen.insert(key.clone()) {
                effective_param_keys.push(key);
            }
        }

        let mut required_runtime_coverage = BTreeMap::new();
        for key in &effective_param_keys {
            let mut covered = 0;
            for host in &self.hosts {
                let missing = format!("runtime-missing-param:{}:{}", host.hostname, key);
                let drift_prefix = format!("runtime-value-drift:{}:{}:", host.hostname, key);
                let failed_key = host.blockers.iter().any(|finding| {
                    finding == &missing || finding.starts_with(&drift_prefix)
                });
                if !failed_key {
                    covered += 1;
                }
            }
            required_runtime_coverage.insert(key.clone(), covered);
        }

        let rollout_ready = self.global_findings.is_empty()
            && self.hosts.iter().all(|host| host.blockers.is_empty() && host.warnings.is_empty());

        RolloutSummary {
            host_count: self.hosts.len(),
            blocked_hosts,
            warning_hosts,
            clean_hosts,
            blocker_count_by_host,
            warning_count_by_host,
            top_finding_codes,
            required_runtime_coverage,
            effective_param_keys,
            rollout_ready,
        }
    }

    pub fn remediation_plan(&self) -> Vec<RemediationAction> {
        let mut host_order = BTreeMap::new();
        for (idx, host) in self.hosts.iter().enumerate() {
            host_order.insert(host.hostname.clone(), idx + 1);
        }

        let mut grouped: BTreeMap<(u8, String, String), Vec<String>> = BTreeMap::new();
        for finding in &self.global_findings {
            let (code, detail) = split_code_detail(finding);
            let priority = remediation_priority(&code);
            add_target(&mut grouped, (priority, code, detail), "global".to_string(), &host_order);
        }
        for host in &self.hosts {
            for finding in host.blockers.iter().chain(host.warnings.iter()) {
                let (code, detail) = split_host_finding(finding, &host.hostname);
                let priority = remediation_priority(&code);
                add_target(&mut grouped, (priority, code, detail), host.hostname.clone(), &host_order);
            }
        }

        grouped
            .into_iter()
            .map(|((priority, code, detail), targets)| RemediationAction {
                priority,
                code,
                detail,
                targets,
            })
            .collect()
    }

    pub fn staged_rollout_waves(&self, max_wave_size: usize) -> Vec<RolloutWave> {
        let wave_size = max_wave_size.max(1);
        let mut candidates: Vec<(usize, String, usize)> = self.hosts.iter().enumerate()
            .filter(|(_, host)| host.blockers.is_empty())
            .map(|(idx, host)| (host.warnings.len(), host.hostname.clone(), idx))
            .collect();
        candidates.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.2.cmp(&b.2)));

        let actions = self.remediation_plan();
        let mut waves = Vec::new();
        for (wave_idx, chunk) in candidates.chunks(wave_size).enumerate() {
            let hosts: Vec<String> = chunk.iter().map(|(_, hostname, _)| hostname.clone()).collect();
            let warning_count = chunk.iter().map(|(warnings, _, _)| *warnings).sum::<usize>();
            let risk_score = self.global_findings.len() + warning_count;
            let required_actions = actions.iter()
                .filter_map(|action| format_wave_action(action, &hosts))
                .collect();
            waves.push(RolloutWave {
                name: format!("wave-{}", wave_idx + 1),
                hosts,
                risk_score,
                required_actions,
            });
        }
        waves
    }
}

fn parse_config(files: &[ConfigFile]) -> ParsedConfig {
    let mut selected: Vec<&ConfigFile> = Vec::new();
    for path in ["/usr/lib/default/grub", "/etc/default/grub"] {
        if let Some(file) = files.iter().find(|f| f.path == path) {
            selected.push(file);
        }
    }

    let mut dropins: Vec<&ConfigFile> = files
        .iter()
        .filter(|f| {
            let Some(name) = f.path.strip_prefix("/etc/default/grub.d/") else {
                return false;
            };
            !name.contains('/') && name.ends_with(".cfg") && !name.starts_with('.')
        })
        .collect();
    dropins.sort_by(|a, b| basename(&a.path).cmp(basename(&b.path)).then(a.path.cmp(&b.path)));
    selected.extend(dropins);

    let mut parsed = ParsedConfig::default();
    for file in selected {
        parsed.effective.source_order.push(file.path.clone());
        for raw in file.content.lines() {
            let line = strip_comment(raw).trim().to_string();
            if line.is_empty() {
                continue;
            }
            let line = line.strip_prefix("export ").unwrap_or(&line).trim();
            let Some((key, value)) = line.split_once('=') else {
                continue;
            };
            let key = key.trim();
            let value = unquote(value.trim());
            match key {
                "GRUB_CMDLINE_LINUX" => parsed.effective.cmdline_linux = split_cmdline(&value),
                "GRUB_CMDLINE_LINUX_DEFAULT" => {
                    parsed.effective.cmdline_linux_default = split_cmdline(&value)
                }
                "GRUB_DISABLE_OS_PROBER" => match parse_bool(&value) {
                    Some(v) => parsed.effective.disable_os_prober = Some(v),
                    None => parsed.bad_bools.push(format!(
                        "bad-bool:{}:GRUB_DISABLE_OS_PROBER:{}",
                        file.path, value
                    )),
                },
                "GRUB_DISTRIBUTOR" => parsed.effective.distributor = Some(value),
                _ => {}
            }
        }
    }
    parsed
}

fn basename(path: &str) -> &str {
    path.rsplit('/').next().unwrap_or(path)
}

fn strip_comment(input: &str) -> String {
    let mut out = String::new();
    let mut single = false;
    let mut double = false;
    let mut escaped = false;
    for ch in input.chars() {
        if escaped {
            out.push(ch);
            escaped = false;
            continue;
        }
        if ch == '\\' && double {
            out.push(ch);
            escaped = true;
            continue;
        }
        match ch {
            '\'' if !double => {
                single = !single;
                out.push(ch);
            }
            '"' if !single => {
                double = !double;
                out.push(ch);
            }
            '#' if !single && !double => break,
            _ => out.push(ch),
        }
    }
    out
}

fn unquote(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.len() >= 2 {
        let bytes = trimmed.as_bytes();
        if (bytes[0] == b'"' && bytes[trimmed.len() - 1] == b'"')
            || (bytes[0] == b'\'' && bytes[trimmed.len() - 1] == b'\'')
        {
            return trimmed[1..trimmed.len() - 1].to_string();
        }
    }
    trimmed.to_string()
}

fn split_cmdline(input: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut cur = String::new();
    let mut single = false;
    let mut double = false;
    let mut escaped = false;
    for ch in input.chars() {
        if escaped {
            cur.push(ch);
            escaped = false;
            continue;
        }
        if ch == '\\' && !single {
            escaped = true;
            continue;
        }
        match ch {
            '\'' if !double => single = !single,
            '"' if !single => double = !double,
            c if c.is_whitespace() && !single && !double => {
                if !cur.is_empty() {
                    tokens.push(cur.clone());
                    cur.clear();
                }
            }
            _ => cur.push(ch),
        }
    }
    if !cur.is_empty() {
        tokens.push(cur);
    }
    tokens
}

fn parse_bool(value: &str) -> Option<bool> {
    match value.trim().to_ascii_lowercase().as_str() {
        "true" | "yes" | "1" => Some(true),
        "false" | "no" | "0" => Some(false),
        _ => None,
    }
}

fn all_effective_tokens(effective: &EffectiveGrubConfig) -> Vec<String> {
    let mut tokens = effective.cmdline_linux.clone();
    tokens.extend(effective.cmdline_linux_default.clone());
    tokens
}

fn key_of(token: &str) -> String {
    token.split_once('=').map(|(k, _)| k).unwrap_or(token).to_string()
}

fn value_of(token: &str) -> Option<String> {
    token.split_once('=').map(|(_, v)| v.to_string())
}

fn keys_for(tokens: &[String]) -> Vec<String> {
    tokens.iter().map(|t| key_of(t)).collect()
}

fn audit_host(
    host: &HostState,
    policy: &RolloutPolicy,
    effective_tokens: &[String],
    effective_keys: &[String],
) -> HostAudit {
    let runtime_tokens = split_cmdline(&host.cmdline_runtime);
    let runtime_keys = keys_for(&runtime_tokens);
    let runtime_key_set: BTreeSet<String> = runtime_keys.iter().cloned().collect();
    let effective_key_set: BTreeSet<String> = effective_keys.iter().cloned().collect();
    let mut runtime_last_values: BTreeMap<String, Option<String>> = BTreeMap::new();
    for token in &runtime_tokens {
        runtime_last_values.insert(key_of(token), value_of(token));
    }
    let mut blockers = Vec::new();

    if host.bootloader != "grub" {
        blockers.push(format!(
            "unsupported-bootloader:{}:{}",
            host.hostname, host.bootloader
        ));
    }
    if version_lt(&host.kernel_version, &policy.min_kernel_version) {
        blockers.push(format!("kernel-too-old:{}:{}", host.hostname, host.kernel_version));
    }
    if policy.require_secure_boot && !host.secure_boot {
        blockers.push(format!("secure-boot-disabled:{}", host.hostname));
    }
    if policy.require_lockdown && !host.lockdown {
        blockers.push(format!("lockdown-disabled:{}", host.hostname));
    }
    if policy.require_iommu {
        let key = iommu_key(&host.arch);
        if !runtime_key_set.contains(key) && !effective_key_set.contains(key) {
            blockers.push(format!("iommu-missing:{}:{}", host.hostname, key));
        }
    }

    for token in &runtime_tokens {
        let key = key_of(token);
        if is_iommu_key(&key) {
            if let Some(value) = value_of(token) {
                if is_weak_iommu_value(&value) {
                    blockers.push(format!(
                        "runtime-weak-iommu:{}:{}:{}",
                        host.hostname, key, value
                    ));
                }
            }
        }
    }

    let mut emitted_effective = BTreeSet::new();
    for key in effective_keys {
        if emitted_effective.insert(key.clone()) && !runtime_key_set.contains(key) {
            blockers.push(format!("runtime-missing-param:{}:{}", host.hostname, key));
        }
    }

    let mut value_order = Vec::new();
    let mut expected_last_values: BTreeMap<String, String> = BTreeMap::new();
    for token in effective_tokens {
        if let Some(expected) = value_of(token) {
            let key = key_of(token);
            if key == "rd.luks.uuid" {
                continue;
            }
            if !expected_last_values.contains_key(&key) {
                value_order.push(key.clone());
            }
            expected_last_values.insert(key, expected);
        }
    }
    for key in value_order {
        if let Some(actual) = runtime_last_values.get(&key) {
            let expected = expected_last_values.get(&key).unwrap();
            let actual_display = actual.clone().unwrap_or_else(|| "<flag>".to_string());
            if actual_display != *expected {
                blockers.push(format!(
                    "runtime-value-drift:{}:{}:{}:{}",
                    host.hostname, key, expected, actual_display
                ));
            }
        }
    }

    let mut seen_runtime = BTreeSet::new();
    let mut emitted_runtime_duplicates = BTreeSet::new();
    for key in &runtime_keys {
        if key != "rd.luks.uuid"
            && !seen_runtime.insert(key.clone())
            && emitted_runtime_duplicates.insert(key.clone())
        {
            blockers.push(format!("runtime-duplicate-param:{}:{}", host.hostname, key));
        }
    }

    for token in &runtime_tokens {
        if key_of(token) == "init" {
            if let Some(value) = value_of(token) {
                if value != "/sbin/init" {
                    blockers.push(format!(
                        "runtime-init-override:{}:{}",
                        host.hostname, value
                    ));
                }
            }
        }
    }

    let forbidden: BTreeSet<String> = policy.forbidden_params.iter().cloned().collect();
    for key in &runtime_keys {
        if forbidden.contains(key) {
            blockers.push(format!("runtime-forbidden-param:{}:{}", host.hostname, key));
        }
    }

    if host.encrypted_root {
        for key in &policy.required_luks_params {
            if !runtime_key_set.contains(key) {
                blockers.push(format!("encrypted-root-missing:{}:{}", host.hostname, key));
            }
        }
    }
    if host.encrypted_root && policy.require_secure_boot && !host.tpm2 {
        blockers.push(format!("encrypted-root-no-tpm2:{}", host.hostname));
    }

    if policy.require_secure_boot {
        for module in &host.modules {
            if module.loaded && !module.builtin && !module.signed {
                blockers.push(format!("unsigned-module:{}:{}", host.hostname, module.name));
            }
        }
    }

    let mut warnings = Vec::new();
    if matches!(host.root_fs.as_str(), "nfs" | "iscsi" | "tmpfs") {
        warnings.push(format!("rootfs-risk:{}:{}", host.hostname, host.root_fs));
    }

    let allowed_debug: BTreeSet<String> = policy.allowed_debug_params.iter().cloned().collect();
    let debug_keys: BTreeSet<&str> = [
        "debug",
        "initcall_debug",
        "ignore_loglevel",
        "systemd.log_level",
        "drm.debug",
    ]
    .into_iter()
    .collect();
    for key in &runtime_keys {
        if debug_keys.contains(key.as_str()) && !allowed_debug.contains(key) {
            warnings.push(format!("debug-param-active:{}:{}", host.hostname, key));
        }
    }

    HostAudit {
        hostname: host.hostname.clone(),
        blockers,
        warnings,
    }
}

fn iommu_key(arch: &str) -> &'static str {
    let lower = arch.to_ascii_lowercase();
    if lower.contains("amd") {
        "amd_iommu"
    } else if lower.contains("x86_64") || lower.contains("intel") {
        "intel_iommu"
    } else {
        "iommu"
    }
}

fn is_iommu_key(key: &str) -> bool {
    matches!(key, "intel_iommu" | "amd_iommu" | "iommu")
}

fn is_weak_iommu_value(value: &str) -> bool {
    matches!(
        value.to_ascii_lowercase().as_str(),
        "off" | "pt" | "passthrough" | "soft"
    )
}

fn version_lt(left: &str, right: &str) -> bool {
    let a = version_nums(left);
    let b = version_nums(right);
    let n = a.len().max(b.len());
    for i in 0..n {
        let av = *a.get(i).unwrap_or(&0);
        let bv = *b.get(i).unwrap_or(&0);
        if av != bv {
            return av < bv;
        }
    }
    false
}

fn version_nums(value: &str) -> Vec<u32> {
    let mut nums = Vec::new();
    let mut cur = String::new();
    for ch in value.chars() {
        if ch.is_ascii_digit() {
            cur.push(ch);
        } else if !cur.is_empty() {
            nums.push(cur.parse().unwrap_or(0));
            cur.clear();
        }
    }
    if !cur.is_empty() {
        nums.push(cur.parse().unwrap_or(0));
    }
    nums
}

fn add_count(counts: &mut BTreeMap<String, usize>, finding: &str) {
    let code = finding.split_once(':').map(|(c, _)| c).unwrap_or(finding);
    *counts.entry(code.to_string()).or_insert(0) += 1;
}

fn split_code_detail(finding: &str) -> (String, String) {
    finding
        .split_once(':')
        .map(|(code, detail)| (code.to_string(), detail.to_string()))
        .unwrap_or_else(|| (finding.to_string(), String::new()))
}

fn split_host_finding(finding: &str, hostname: &str) -> (String, String) {
    let Some((code, rest)) = finding.split_once(':') else {
        return (finding.to_string(), String::new());
    };
    let prefix = format!("{hostname}:");
    if rest == hostname {
        (code.to_string(), String::new())
    } else if let Some(detail) = rest.strip_prefix(&prefix) {
        (code.to_string(), detail.to_string())
    } else {
        (code.to_string(), rest.to_string())
    }
}

fn remediation_priority(code: &str) -> u8 {
    match code {
        "unsupported-bootloader"
        | "kernel-too-old"
        | "secure-boot-disabled"
        | "lockdown-disabled"
        | "encrypted-root-no-tpm2"
        | "unsigned-module"
        | "runtime-init-override"
        | "runtime-forbidden-param"
        | "forbidden-param"
        | "bad-bool" => 0,
        "missing-required-param"
        | "missing-luks-param"
        | "encrypted-root-missing"
        | "iommu-missing"
        | "weak-iommu-setting"
        | "runtime-weak-iommu"
        | "runtime-missing-param"
        | "runtime-value-drift" => 1,
        "duplicate-param" | "runtime-duplicate-param" | "conflict-param" | "os-prober-enabled" => 2,
        "rootfs-risk" | "debug-param-active" => 3,
        _ => 4,
    }
}

fn add_target(
    grouped: &mut BTreeMap<(u8, String, String), Vec<String>>,
    key: (u8, String, String),
    target: String,
    host_order: &BTreeMap<String, usize>,
) {
    let targets = grouped.entry(key).or_default();
    if targets.iter().any(|existing| existing == &target) {
        return;
    }
    targets.push(target);
    targets.sort_by(|a, b| target_rank(a, host_order).cmp(&target_rank(b, host_order)).then_with(|| a.cmp(b)));
}

fn target_rank(target: &str, host_order: &BTreeMap<String, usize>) -> usize {
    if target == "global" {
        0
    } else {
        *host_order.get(target).unwrap_or(&usize::MAX)
    }
}

fn format_wave_action(action: &RemediationAction, wave_hosts: &[String]) -> Option<String> {
    let mut targets = Vec::new();
    for target in &action.targets {
        if target == "global" || wave_hosts.iter().any(|host| host == target) {
            targets.push(target.clone());
        }
    }
    if targets.is_empty() {
        return None;
    }
    Some(format!(
        "{}:{}:{}:{}",
        action.priority,
        action.code,
        action.detail,
        targets.join(",")
    ))
}
RS

cd "$TASK_DIR"
cargo test --release --locked
