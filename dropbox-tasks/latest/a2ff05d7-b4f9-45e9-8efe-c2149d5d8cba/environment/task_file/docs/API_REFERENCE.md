# API Reference

The verifier constructs `GrubRollout` values directly, calls `GrubRollout::audit`, and calls derived methods on the returned `AuditReport`.

Do not rename or remove these public types, fields, or methods:

```rust
use std::collections::BTreeMap;

impl GrubRollout {
    pub fn audit(&self) -> AuditReport;
}

impl AuditReport {
    pub fn rollout_summary(&self) -> RolloutSummary;
    pub fn remediation_plan(&self) -> Vec<RemediationAction>;
    pub fn staged_rollout_waves(&self, max_wave_size: usize) -> Vec<RolloutWave>;
}

pub struct GrubRollout {
    pub files: Vec<ConfigFile>,
    pub hosts: Vec<HostState>,
    pub policy: RolloutPolicy,
}

pub struct ConfigFile {
    pub path: String,
    pub content: String,
}

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

pub struct ModuleState {
    pub name: String,
    pub loaded: bool,
    pub builtin: bool,
    pub signed: bool,
}

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

pub struct AuditReport {
    pub effective: EffectiveGrubConfig,
    pub hosts: Vec<HostAudit>,
    pub global_findings: Vec<String>,
    pub finding_count_by_code: BTreeMap<String, usize>,
}

pub struct EffectiveGrubConfig {
    pub source_order: Vec<String>,
    pub cmdline_linux: Vec<String>,
    pub cmdline_linux_default: Vec<String>,
    pub disable_os_prober: Option<bool>,
    pub distributor: Option<String>,
}

pub struct HostAudit {
    pub hostname: String,
    pub blockers: Vec<String>,
    pub warnings: Vec<String>,
}

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

pub struct RemediationAction {
    pub priority: u8,
    pub code: String,
    pub detail: String,
    pub targets: Vec<String>,
}

pub struct RolloutWave {
    pub name: String,
    pub hosts: Vec<String>,
    pub risk_score: usize,
    pub required_actions: Vec<String>,
}
```

`AuditReport.hosts` keeps input host order. `global_findings` is sorted lexicographically. `finding_count_by_code` counts global findings, host blockers, and host warnings by the substring before the first `:`.
