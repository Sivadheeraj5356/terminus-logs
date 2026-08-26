use std::collections::BTreeMap;

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

impl GrubRollout {
    pub fn audit(&self) -> AuditReport {
        AuditReport {
            effective: EffectiveGrubConfig {
                source_order: Vec::new(),
                cmdline_linux: Vec::new(),
                cmdline_linux_default: Vec::new(),
                disable_os_prober: None,
                distributor: None,
            },
            hosts: self
                .hosts
                .iter()
                .map(|h| HostAudit {
                    hostname: h.hostname.clone(),
                    blockers: Vec::new(),
                    warnings: Vec::new(),
                })
                .collect(),
            global_findings: Vec::new(),
            finding_count_by_code: BTreeMap::new(),
        }
    }
}

impl AuditReport {
    pub fn rollout_summary(&self) -> RolloutSummary {
        RolloutSummary {
            host_count: self.hosts.len(),
            blocked_hosts: Vec::new(),
            warning_hosts: Vec::new(),
            clean_hosts: Vec::new(),
            blocker_count_by_host: BTreeMap::new(),
            warning_count_by_host: BTreeMap::new(),
            top_finding_codes: Vec::new(),
            required_runtime_coverage: BTreeMap::new(),
            effective_param_keys: Vec::new(),
            rollout_ready: false,
        }
    }

    pub fn remediation_plan(&self) -> Vec<RemediationAction> {
        Vec::new()
    }

    pub fn staged_rollout_waves(&self, max_wave_size: usize) -> Vec<RolloutWave> {
        let _ = max_wave_size;
        Vec::new()
    }
}
