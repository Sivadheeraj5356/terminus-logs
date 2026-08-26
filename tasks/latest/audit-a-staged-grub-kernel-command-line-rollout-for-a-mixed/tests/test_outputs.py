import os
import subprocess
from pathlib import Path


TASK_DIR = Path(os.environ.get("TASK_DIR", "/app/task_file"))


HIDDEN_TESTS = r'''
use bootlineguard::*;

fn policy() -> RolloutPolicy {
    RolloutPolicy {
        min_kernel_version: "5.15.0".to_string(),
        require_secure_boot: true,
        require_lockdown: true,
        require_iommu: true,
        forbidden_params: vec!["selinux".to_string(), "init".to_string(), "debug".to_string()],
        required_params: vec!["audit".to_string(), "slab_nomerge".to_string()],
        allowed_debug_params: vec!["drm.debug".to_string()],
        required_luks_params: vec!["rd.luks.uuid".to_string(), "rd.luks.options".to_string()],
    }
}

fn file(path: &str, content: &str) -> ConfigFile {
    ConfigFile { path: path.to_string(), content: content.to_string() }
}

fn module(name: &str, loaded: bool, builtin: bool, signed: bool) -> ModuleState {
    ModuleState { name: name.to_string(), loaded, builtin, signed }
}

fn host(
    name: &str,
    bootloader: &str,
    arch: &str,
    secure_boot: bool,
    lockdown: bool,
    root_fs: &str,
    encrypted_root: bool,
    kernel_version: &str,
    runtime: &str,
    modules: Vec<ModuleState>,
) -> HostState {
    HostState {
        hostname: name.to_string(),
        bootloader: bootloader.to_string(),
        arch: arch.to_string(),
        secure_boot,
        lockdown,
        tpm2: false,
        root_fs: root_fs.to_string(),
        encrypted_root,
        kernel_version: kernel_version.to_string(),
        cmdline_runtime: runtime.to_string(),
        modules,
    }
}

#[test]
fn config_precedence_quotes_dropins_and_effective_values_work() {
    let rollout = GrubRollout {
        files: vec![
            file("/tmp/grub", "GRUB_CMDLINE_LINUX=\"init=/bin/sh\"\n"),
            file("/usr/lib/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 quiet\"\nGRUB_CMDLINE_LINUX_DEFAULT='slab_nomerge intel_iommu=on'\nGRUB_DISABLE_OS_PROBER=false\n"),
            file("/etc/default/grub.d/.hidden.cfg", "GRUB_CMDLINE_LINUX=\"selinux=0\"\n"),
            file("/etc/default/grub.d/20-extra.cfg", "export GRUB_DISTRIBUTOR='Debian # fleet'\nGRUB_CMDLINE_LINUX_DEFAULT=\"rd.luks.uuid=abc rd.luks.options=discard\"\n"),
            file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge\" # outside comment\nGRUB_DISABLE_OS_PROBER=yes\n"),
            file("/etc/default/grub.d/10-base.cfg", "GRUB_CMDLINE_LINUX_DEFAULT=\"quiet intel_iommu=on\"\n"),
        ],
        hosts: vec![],
        policy: policy(),
    };

    let report = rollout.audit();
    assert_eq!(report.effective.source_order, vec![
        "/usr/lib/default/grub",
        "/etc/default/grub",
        "/etc/default/grub.d/10-base.cfg",
        "/etc/default/grub.d/20-extra.cfg",
    ]);
    assert_eq!(report.effective.cmdline_linux, vec!["audit=1", "slab_nomerge"]);
    assert_eq!(report.effective.cmdline_linux_default, vec!["rd.luks.uuid=abc", "rd.luks.options=discard"]);
    assert_eq!(report.effective.disable_os_prober, Some(true));
    assert_eq!(report.effective.distributor.as_deref(), Some("Debian # fleet"));
    assert!(report.global_findings.is_empty());
}

#[test]
fn parser_handles_inner_quotes_hashes_unquoted_scalars_and_resets() {
    let rollout = GrubRollout {
        files: vec![
            file("/usr/lib/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 root='LABEL=prod root' debug\"\nGRUB_CMDLINE_LINUX_DEFAULT=\"quiet\"\nGRUB_DISABLE_OS_PROBER=NO\nGRUB_DISTRIBUTOR=BaseDistro\n"),
            file("/etc/default/grub", "export GRUB_CMDLINE_LINUX='audit=1 module_blacklist=\"bad driver\" rd.luks.uuid=a rd.luks.options=discard' # outside\nGRUB_CMDLINE_LINUX_DEFAULT=\"intel_iommu=on systemd.log_level='debug verbose'\"\nGRUB_DISTRIBUTOR=\"Prod # not comment\"\n"),
            file("/etc/default/grub.d/05-reset.cfg", "GRUB_CMDLINE_LINUX_DEFAULT=\n"),
            file("/etc/default/grub.d/10-final.cfg", "GRUB_CMDLINE_LINUX_DEFAULT=\"slab_nomerge intel_iommu=on\"\n"),
        ],
        hosts: vec![],
        policy: RolloutPolicy {
            forbidden_params: vec![],
            allowed_debug_params: vec!["systemd.log_level".to_string()],
            ..policy()
        },
    };

    let report = rollout.audit();
    assert_eq!(report.effective.cmdline_linux, vec![
        "audit=1",
        "module_blacklist=bad driver",
        "rd.luks.uuid=a",
        "rd.luks.options=discard",
    ]);
    assert_eq!(report.effective.cmdline_linux_default, vec!["slab_nomerge", "intel_iommu=on"]);
    assert_eq!(report.effective.disable_os_prober, Some(false));
    assert_eq!(report.effective.distributor.as_deref(), Some("Prod # not comment"));
    assert_eq!(report.global_findings, vec!["os-prober-enabled"]);
}

#[test]
fn global_findings_are_sorted_and_counted() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"quiet debug selinux=0 audit=0 audit=1 nomodeset i915.modeset=0\"\nGRUB_DISABLE_OS_PROBER=maybe\n")],
        hosts: vec![],
        policy: policy(),
    };

    let report = rollout.audit();
    assert_eq!(report.global_findings, vec![
        "bad-bool:/etc/default/grub:GRUB_DISABLE_OS_PROBER:maybe",
        "conflict-param:nomodeset:i915.modeset",
        "conflict-param:quiet:debug",
        "duplicate-param:audit",
        "forbidden-param:debug",
        "forbidden-param:selinux",
        "missing-luks-param:rd.luks.options",
        "missing-luks-param:rd.luks.uuid",
        "missing-required-param:slab_nomerge",
    ]);
    assert_eq!(report.finding_count_by_code.get("missing-luks-param"), Some(&2));
    assert_eq!(report.finding_count_by_code.get("forbidden-param"), Some(&2));
}

#[test]
fn host_blockers_follow_policy_and_runtime_order() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge rd.luks.uuid=abc rd.luks.options=discard intel_iommu=on\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![host(
            "jump-a",
            "systemd-boot",
            "x86_64-intel",
            false,
            false,
            "nfs",
            true,
            "5.10.42-custom",
            "audit=1 debug init=/bin/bash rd.luks.uuid=abc",
            vec![
                module("wireguard", true, false, false),
                module("ext4", true, true, false),
                module("kvm", false, false, false),
            ],
        )],
        policy: policy(),
    };

    let report = rollout.audit();
    assert_eq!(report.hosts[0].blockers, vec![
        "unsupported-bootloader:jump-a:systemd-boot",
        "kernel-too-old:jump-a:5.10.42-custom",
        "secure-boot-disabled:jump-a",
        "lockdown-disabled:jump-a",
        "runtime-missing-param:jump-a:slab_nomerge",
        "runtime-missing-param:jump-a:rd.luks.options",
        "runtime-missing-param:jump-a:intel_iommu",
        "runtime-init-override:jump-a:/bin/bash",
        "runtime-forbidden-param:jump-a:debug",
        "runtime-forbidden-param:jump-a:init",
        "encrypted-root-missing:jump-a:rd.luks.options",
        "encrypted-root-no-tpm2:jump-a",
        "unsigned-module:jump-a:wireguard",
    ]);
    assert_eq!(report.hosts[0].warnings, vec![
        "rootfs-risk:jump-a:nfs",
        "debug-param-active:jump-a:debug",
    ]);
    assert_eq!(report.finding_count_by_code.get("runtime-missing-param"), Some(&3));
}

#[test]
fn architecture_iommu_and_debug_allowlist_are_handled() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge amd_iommu=on rd.luks.uuid=a rd.luks.uuid=b rd.luks.options=discard quiet\"\nGRUB_DISABLE_OS_PROBER=false\n")],
        hosts: vec![host(
            "db-a",
            "grub",
            "x86_64-amd",
            true,
            true,
            "xfs",
            false,
            "6.1.12",
            "audit=1 slab_nomerge amd_iommu=on rd.luks.uuid=a rd.luks.options=discard drm.debug=0x1 quiet",
            vec![module("zfs", true, false, true)],
        )],
        policy: policy(),
    };

    let report = rollout.audit();
    assert_eq!(report.global_findings, vec!["os-prober-enabled"]);
    assert!(report.hosts[0].blockers.is_empty());
    assert!(report.hosts[0].warnings.is_empty());
    assert_eq!(report.finding_count_by_code.get("duplicate-param"), None);
    assert_eq!(report.finding_count_by_code.get("os-prober-enabled"), Some(&1));
}

#[test]
fn non_x86_iommu_conflicts_and_runtime_quoted_tokens_are_checked() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge iommu.passthrough=0\"\nGRUB_CMDLINE_LINUX_DEFAULT=\"systemd.unified_cgroup_hierarchy=1 cgroup_no_v1=all iommu=on rd.luks.uuid=x rd.luks.options=discard\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![host(
            "edge-arm",
            "grub",
            "aarch64",
            true,
            true,
            "tmpfs",
            false,
            "5.15.0",
            "audit=1 slab_nomerge 'iommu=on' rd.luks.uuid=x rd.luks.options=discard systemd.log_level=debug",
            vec![],
        )],
        policy: policy(),
    };

    let report = rollout.audit();
    assert_eq!(report.global_findings, vec!["conflict-param:systemd.unified_cgroup_hierarchy:cgroup_no_v1"]);
    assert_eq!(report.hosts[0].blockers, vec![
        "runtime-missing-param:edge-arm:iommu.passthrough",
        "runtime-missing-param:edge-arm:systemd.unified_cgroup_hierarchy",
        "runtime-missing-param:edge-arm:cgroup_no_v1",
    ]);
    assert_eq!(report.hosts[0].warnings, vec![
        "rootfs-risk:edge-arm:tmpfs",
        "debug-param-active:edge-arm:systemd.log_level",
    ]);
}

#[test]
fn empty_resets_and_missing_iommu_are_reported() {
    let rollout = GrubRollout {
        files: vec![
            file("/usr/lib/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on\"\nGRUB_CMDLINE_LINUX_DEFAULT=\"quiet\"\nGRUB_DISABLE_OS_PROBER=true\n"),
            file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge\"\nGRUB_CMDLINE_LINUX_DEFAULT=\n"),
        ],
        hosts: vec![host(
            "compute-a",
            "grub",
            "x86_64-intel",
            true,
            true,
            "ext4",
            false,
            "6.2.0",
            "audit=1 slab_nomerge",
            vec![],
        )],
        policy: RolloutPolicy {
            required_luks_params: vec![],
            ..policy()
        },
    };

    let report = rollout.audit();
    assert_eq!(report.effective.cmdline_linux, vec!["audit=1", "slab_nomerge"]);
    assert!(report.effective.cmdline_linux_default.is_empty());
    assert!(report.global_findings.is_empty());
    assert_eq!(report.hosts[0].blockers, vec!["iommu-missing:compute-a:intel_iommu"]);
    assert!(report.hosts[0].warnings.is_empty());
    assert_eq!(report.finding_count_by_code.get("iommu-missing"), Some(&1));
}

#[test]
fn runtime_value_drift_and_duplicate_runtime_params_are_blockers() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on mitigations=auto\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![host(
            "node-drift",
            "grub",
            "x86_64-intel",
            true,
            true,
            "ext4",
            false,
            "6.2.0",
            "audit=0 audit=0 slab_nomerge intel_iommu=off mitigations=auto",
            vec![],
        )],
        policy: RolloutPolicy {
            required_luks_params: vec![],
            ..policy()
        },
    };

    let report = rollout.audit();
    assert!(report.global_findings.is_empty());
    assert_eq!(report.hosts[0].blockers, vec![
        "runtime-weak-iommu:node-drift:intel_iommu:off",
        "runtime-value-drift:node-drift:audit:1:0",
        "runtime-value-drift:node-drift:intel_iommu:on:off",
        "runtime-duplicate-param:node-drift:audit",
    ]);
    assert!(report.hosts[0].warnings.is_empty());
    assert_eq!(report.finding_count_by_code.get("runtime-weak-iommu"), Some(&1));
    assert_eq!(report.finding_count_by_code.get("runtime-value-drift"), Some(&2));
    assert_eq!(report.finding_count_by_code.get("runtime-duplicate-param"), Some(&1));
}

#[test]
fn weak_iommu_settings_are_not_treated_as_safe_presence() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=pt rd.luks.uuid=abc rd.luks.options=discard\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![HostState {
            hostname: "weak-iommu-a".to_string(),
            bootloader: "grub".to_string(),
            arch: "x86_64-intel".to_string(),
            secure_boot: true,
            lockdown: true,
            tpm2: false,
            root_fs: "ext4".to_string(),
            encrypted_root: true,
            kernel_version: "6.4.1".to_string(),
            cmdline_runtime: "audit=1 slab_nomerge intel_iommu=off rd.luks.uuid=abc rd.luks.options=discard".to_string(),
            modules: vec![],
        }],
        policy: policy(),
    };

    let report = rollout.audit();
    assert_eq!(report.global_findings, vec!["weak-iommu-setting:intel_iommu:pt"]);
    assert_eq!(report.hosts[0].blockers, vec![
        "runtime-weak-iommu:weak-iommu-a:intel_iommu:off",
        "runtime-value-drift:weak-iommu-a:intel_iommu:pt:off",
        "encrypted-root-no-tpm2:weak-iommu-a",
    ]);
    assert!(report.hosts[0].warnings.is_empty());
    assert_eq!(report.finding_count_by_code.get("weak-iommu-setting"), Some(&1));
    assert_eq!(report.finding_count_by_code.get("runtime-weak-iommu"), Some(&1));
    assert_eq!(report.finding_count_by_code.get("encrypted-root-no-tpm2"), Some(&1));
}

#[test]
fn generic_iommu_key_and_weak_presence_are_handled_for_non_x86_arches() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge iommu=soft rd.luks.uuid=z rd.luks.options=discard\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![host(
            "edge-riscv",
            "grub",
            "riscv64",
            true,
            true,
            "iscsi",
            false,
            "5.15.0-vendor",
            "audit=1 slab_nomerge iommu=soft rd.luks.uuid=z rd.luks.options=discard initcall_debug ignore_loglevel",
            vec![],
        )],
        policy: RolloutPolicy {
            allowed_debug_params: vec!["ignore_loglevel".to_string()],
            ..policy()
        },
    };

    let report = rollout.audit();
    assert_eq!(report.global_findings, vec!["weak-iommu-setting:iommu:soft"]);
    assert_eq!(report.hosts[0].blockers, vec!["runtime-weak-iommu:edge-riscv:iommu:soft"]);
    assert_eq!(report.hosts[0].warnings, vec![
        "rootfs-risk:edge-riscv:iscsi",
        "debug-param-active:edge-riscv:initcall_debug",
    ]);
}

#[test]
fn runtime_duplicate_order_and_last_value_drift_are_deterministic() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on mitigations=auto rd.luks.uuid=a rd.luks.options=discard\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![host(
            "dup-order",
            "grub",
            "x86_64-intel",
            true,
            true,
            "ext4",
            false,
            "5.15.0",
            "audit=0 slab_nomerge=1 audit=1 rd.luks.uuid=a rd.luks.uuid=b rd.luks.options=discard intel_iommu=on mitigations=off slab_nomerge",
            vec![],
        )],
        policy: policy(),
    };

    let report = rollout.audit();
    assert_eq!(report.hosts[0].blockers, vec![
        "runtime-value-drift:dup-order:mitigations:auto:off",
        "runtime-duplicate-param:dup-order:audit",
        "runtime-duplicate-param:dup-order:slab_nomerge",
    ]);
    assert_eq!(report.finding_count_by_code.get("runtime-duplicate-param"), Some(&2));
}

#[test]
fn mixed_architecture_iommu_matrix_uses_effective_or_runtime_presence() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge rd.luks.uuid=x rd.luks.options=discard\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![
            host("amd-runtime", "grub", "amd64", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge amd_iommu=pt rd.luks.uuid=x rd.luks.options=discard", vec![]),
            host("intel-missing", "grub", "x86_64", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge rd.luks.uuid=x rd.luks.options=discard", vec![]),
            host("arm-runtime", "grub", "arm64", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge iommu=on rd.luks.uuid=x rd.luks.options=discard", vec![]),
        ],
        policy: policy(),
    };

    let report = rollout.audit();
    assert_eq!(report.hosts[0].blockers, vec!["runtime-weak-iommu:amd-runtime:amd_iommu:pt"]);
    assert_eq!(report.hosts[1].blockers, vec!["iommu-missing:intel-missing:intel_iommu"]);
    assert!(report.hosts[2].blockers.is_empty());
    assert_eq!(report.finding_count_by_code.get("runtime-weak-iommu"), Some(&1));
    assert_eq!(report.finding_count_by_code.get("iommu-missing"), Some(&1));
}

#[test]
fn config_selection_ignores_nested_and_non_cfg_dropins_while_sorting_basenames() {
    let rollout = GrubRollout {
        files: vec![
            file("/etc/default/grub.d/90-late.cfg", "GRUB_CMDLINE_LINUX_DEFAULT=\"late=1\"\n"),
            file("/etc/default/grub.d/10-base.conf", "GRUB_CMDLINE_LINUX=\"bad=1\"\n"),
            file("/etc/default/grub.d/sub/20-nested.cfg", "GRUB_CMDLINE_LINUX=\"bad=2\"\n"),
            file("/etc/default/grub.d/02-mid.cfg", "GRUB_CMDLINE_LINUX_DEFAULT=\"mid=1\"\n"),
            file("/usr/lib/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1\"\nGRUB_CMDLINE_LINUX_DEFAULT=\"vendor=1\"\n"),
            file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge rd.luks.uuid=a rd.luks.options=discard\"\nGRUB_DISABLE_OS_PROBER=true\n"),
        ],
        hosts: vec![],
        policy: policy(),
    };

    let report = rollout.audit();
    assert_eq!(report.effective.source_order, vec![
        "/usr/lib/default/grub",
        "/etc/default/grub",
        "/etc/default/grub.d/02-mid.cfg",
        "/etc/default/grub.d/90-late.cfg",
    ]);
    assert_eq!(report.effective.cmdline_linux, vec!["audit=1", "slab_nomerge", "rd.luks.uuid=a", "rd.luks.options=discard"]);
    assert_eq!(report.effective.cmdline_linux_default, vec!["late=1"]);
    assert!(report.global_findings.is_empty());
}

#[test]
fn rollout_summary_aggregates_hosts_codes_and_runtime_coverage() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on mitigations=auto debug\"\nGRUB_DISABLE_OS_PROBER=false\n")],
        hosts: vec![
            host(
                "blocked-a",
                "grub",
                "x86_64-intel",
                true,
                true,
                "ext4",
                false,
                "6.2.0",
                "audit=0 slab_nomerge intel_iommu=off mitigations=auto debug",
                vec![],
            ),
            host(
                "warn-a",
                "grub",
                "x86_64-intel",
                true,
                true,
                "nfs",
                false,
                "6.2.0",
                "audit=1 slab_nomerge intel_iommu=on mitigations=auto debug systemd.log_level=debug",
                vec![],
            ),
            host(
                "clean-a",
                "grub",
                "x86_64-intel",
                true,
                true,
                "ext4",
                false,
                "6.2.0",
                "audit=1 slab_nomerge intel_iommu=on mitigations=auto debug",
                vec![],
            ),
        ],
        policy: RolloutPolicy {
            forbidden_params: vec![],
            required_luks_params: vec![],
            allowed_debug_params: vec!["debug".to_string()],
            ..policy()
        },
    };

    let report = rollout.audit();
    let summary = report.rollout_summary();
    assert_eq!(summary.host_count, 3);
    assert_eq!(summary.blocked_hosts, vec!["blocked-a"]);
    assert_eq!(summary.warning_hosts, vec!["warn-a"]);
    assert_eq!(summary.clean_hosts, vec!["clean-a"]);
    assert_eq!(summary.blocker_count_by_host.get("blocked-a"), Some(&3));
    assert_eq!(summary.warning_count_by_host.get("warn-a"), Some(&2));
    assert_eq!(summary.effective_param_keys, vec!["audit", "slab_nomerge", "intel_iommu", "mitigations", "debug"]);
    assert_eq!(summary.required_runtime_coverage.get("audit"), Some(&2));
    assert_eq!(summary.required_runtime_coverage.get("slab_nomerge"), Some(&3));
    assert_eq!(summary.required_runtime_coverage.get("intel_iommu"), Some(&2));
    assert_eq!(summary.required_runtime_coverage.get("mitigations"), Some(&3));
    assert_eq!(summary.required_runtime_coverage.get("debug"), Some(&3));
    assert_eq!(summary.top_finding_codes, vec![
        ("runtime-value-drift".to_string(), 2),
        ("debug-param-active".to_string(), 1),
        ("os-prober-enabled".to_string(), 1),
        ("rootfs-risk".to_string(), 1),
        ("runtime-weak-iommu".to_string(), 1),
    ]);
    assert!(!summary.rollout_ready);

    let ready_rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![host(
            "ready-a",
            "grub",
            "x86_64-intel",
            true,
            true,
            "ext4",
            false,
            "6.2.0",
            "audit=1 slab_nomerge intel_iommu=on",
            vec![],
        )],
        policy: RolloutPolicy {
            required_luks_params: vec![],
            ..policy()
        },
    };
    let ready_summary = ready_rollout.audit().rollout_summary();
    assert!(ready_summary.rollout_ready);
    assert_eq!(ready_summary.clean_hosts, vec!["ready-a"]);
    assert_eq!(ready_summary.top_finding_codes, Vec::<(String, usize)>::new());
}

#[test]
fn remediation_plan_groups_prioritizes_and_orders_targets() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on debug\"\nGRUB_DISABLE_OS_PROBER=false\n")],
        hosts: vec![
            host(
                "alpha",
                "grub",
                "x86_64-intel",
                true,
                true,
                "nfs",
                false,
                "6.2.0",
                "audit=0 slab_nomerge intel_iommu=off debug systemd.log_level=debug",
                vec![],
            ),
            host(
                "beta",
                "systemd-boot",
                "x86_64-intel",
                true,
                true,
                "ext4",
                false,
                "6.2.0",
                "audit=1 slab_nomerge debug",
                vec![],
            ),
            host(
                "gamma",
                "grub",
                "x86_64-intel",
                true,
                true,
                "tmpfs",
                false,
                "6.2.0",
                "audit=1 slab_nomerge intel_iommu=on debug systemd.log_level=debug",
                vec![],
            ),
        ],
        policy: RolloutPolicy {
            forbidden_params: vec![],
            required_luks_params: vec![],
            allowed_debug_params: vec!["debug".to_string()],
            ..policy()
        },
    };

    let plan = rollout.audit().remediation_plan();
    assert_eq!(plan.iter().map(|a| (&a.priority, a.code.as_str(), a.detail.as_str(), a.targets.clone())).collect::<Vec<_>>(), vec![
        (&0, "unsupported-bootloader", "systemd-boot", vec!["beta".to_string()]),
        (&1, "runtime-missing-param", "intel_iommu", vec!["beta".to_string()]),
        (&1, "runtime-value-drift", "audit:1:0", vec!["alpha".to_string()]),
        (&1, "runtime-value-drift", "intel_iommu:on:off", vec!["alpha".to_string()]),
        (&1, "runtime-weak-iommu", "intel_iommu:off", vec!["alpha".to_string()]),
        (&2, "os-prober-enabled", "", vec!["global".to_string()]),
        (&3, "debug-param-active", "systemd.log_level", vec!["alpha".to_string(), "gamma".to_string()]),
        (&3, "rootfs-risk", "nfs", vec!["alpha".to_string()]),
        (&3, "rootfs-risk", "tmpfs", vec!["gamma".to_string()]),
    ]);
}

#[test]
fn staged_rollout_waves_exclude_blocked_hosts_and_intersect_actions() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on debug\"\nGRUB_DISABLE_OS_PROBER=false\n")],
        hosts: vec![
            host(
                "blocked-a",
                "grub",
                "x86_64-intel",
                true,
                true,
                "ext4",
                false,
                "6.2.0",
                "audit=1 slab_nomerge debug",
                vec![],
            ),
            host(
                "clean-1",
                "grub",
                "x86_64-intel",
                true,
                true,
                "ext4",
                false,
                "6.2.0",
                "audit=1 slab_nomerge intel_iommu=on debug",
                vec![],
            ),
            host(
                "warn-1",
                "grub",
                "x86_64-intel",
                true,
                true,
                "nfs",
                false,
                "6.2.0",
                "audit=1 slab_nomerge intel_iommu=on debug systemd.log_level=debug",
                vec![],
            ),
            host(
                "clean-2",
                "grub",
                "x86_64-intel",
                true,
                true,
                "ext4",
                false,
                "6.2.0",
                "audit=1 slab_nomerge intel_iommu=on debug",
                vec![],
            ),
            host(
                "warn-2",
                "grub",
                "x86_64-intel",
                true,
                true,
                "tmpfs",
                false,
                "6.2.0",
                "audit=1 slab_nomerge intel_iommu=on debug systemd.log_level=debug",
                vec![],
            ),
        ],
        policy: RolloutPolicy {
            forbidden_params: vec![],
            required_luks_params: vec![],
            allowed_debug_params: vec!["debug".to_string()],
            ..policy()
        },
    };

    let waves = rollout.audit().staged_rollout_waves(2);
    assert_eq!(waves.len(), 2);
    assert_eq!(waves[0].name, "wave-1");
    assert_eq!(waves[0].hosts, vec!["clean-1", "clean-2"]);
    assert_eq!(waves[0].risk_score, 1);
    assert_eq!(waves[0].required_actions, vec!["2:os-prober-enabled::global"]);
    assert_eq!(waves[1].name, "wave-2");
    assert_eq!(waves[1].hosts, vec!["warn-1", "warn-2"]);
    assert_eq!(waves[1].risk_score, 5);
    assert_eq!(waves[1].required_actions, vec![
        "2:os-prober-enabled::global",
        "3:debug-param-active:systemd.log_level:warn-1,warn-2",
        "3:rootfs-risk:nfs:warn-1",
        "3:rootfs-risk:tmpfs:warn-2",
    ]);

    let singleton_waves = rollout.audit().staged_rollout_waves(0);
    assert_eq!(singleton_waves.len(), 4);
    assert_eq!(singleton_waves[0].hosts, vec!["clean-1"]);
    assert_eq!(singleton_waves[1].hosts, vec!["clean-2"]);
    assert_eq!(singleton_waves[2].hosts, vec!["warn-1"]);
    assert_eq!(singleton_waves[3].hosts, vec!["warn-2"]);
}

#[test]
fn summary_top_codes_truncate_to_five_with_lexicographic_ties() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on debug\"\nGRUB_DISABLE_OS_PROBER=false\n")],
        hosts: vec![
            host("h1", "grub", "x86_64-intel", true, true, "nfs", false, "6.2.0", "audit=0 slab_nomerge intel_iommu=off debug systemd.log_level=debug initcall_debug", vec![]),
            host("h2", "grub", "x86_64-intel", true, true, "tmpfs", false, "6.2.0", "audit=0 slab_nomerge debug systemd.log_level=debug initcall_debug", vec![]),
            host("h3", "grub", "x86_64-intel", true, true, "iscsi", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug systemd.log_level=debug", vec![]),
        ],
        policy: RolloutPolicy {
            forbidden_params: vec![],
            required_luks_params: vec![],
            allowed_debug_params: vec!["debug".to_string()],
            ..policy()
        },
    };

    let summary = rollout.audit().rollout_summary();
    assert_eq!(summary.top_finding_codes, vec![
        ("debug-param-active".to_string(), 5),
        ("rootfs-risk".to_string(), 3),
        ("runtime-value-drift".to_string(), 3),
        ("os-prober-enabled".to_string(), 1),
        ("runtime-missing-param".to_string(), 1),
    ]);
    assert_eq!(summary.required_runtime_coverage.get("audit"), Some(&1));
    assert_eq!(summary.required_runtime_coverage.get("intel_iommu"), Some(&1));
}

#[test]
fn remediation_deduplicates_details_and_preserves_global_then_host_order() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on debug init=/bin/bash\"\nGRUB_DISABLE_OS_PROBER=maybe\n")],
        hosts: vec![
            host("zeta", "grub", "x86_64-intel", true, true, "nfs", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug init=/bin/bash", vec![]),
            host("alpha", "grub", "x86_64-intel", true, true, "nfs", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug init=/bin/bash", vec![]),
        ],
        policy: RolloutPolicy {
            required_luks_params: vec![],
            allowed_debug_params: vec!["debug".to_string()],
            ..policy()
        },
    };

    let plan = rollout.audit().remediation_plan();
    let simplified = plan.iter()
        .map(|a| (a.priority, a.code.as_str(), a.detail.as_str(), a.targets.clone()))
        .collect::<Vec<_>>();
    assert!(simplified.contains(&(0, "bad-bool", "/etc/default/grub:GRUB_DISABLE_OS_PROBER:maybe", vec!["global".to_string()])));
    assert!(simplified.contains(&(0, "forbidden-param", "init", vec!["global".to_string()])));
    assert!(simplified.contains(&(0, "runtime-forbidden-param", "init", vec!["zeta".to_string(), "alpha".to_string()])));
    assert!(simplified.contains(&(0, "runtime-init-override", "/bin/bash", vec!["zeta".to_string(), "alpha".to_string()])));
    assert!(simplified.contains(&(3, "rootfs-risk", "nfs", vec!["zeta".to_string(), "alpha".to_string()])));
}

#[test]
fn remediation_groups_same_missing_runtime_detail_across_non_adjacent_hosts() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on mitigations=auto\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![
            host("first", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge", vec![]),
            host("middle", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on mitigations=auto", vec![]),
            host("last", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge", vec![]),
        ],
        policy: RolloutPolicy {
            required_luks_params: vec![],
            ..policy()
        },
    };

    let plan = rollout.audit().remediation_plan();
    let missing_iommu = plan.iter()
        .find(|a| a.code == "runtime-missing-param" && a.detail == "intel_iommu")
        .unwrap();
    let missing_mitigations = plan.iter()
        .find(|a| a.code == "runtime-missing-param" && a.detail == "mitigations")
        .unwrap();
    assert_eq!(missing_iommu.targets, vec!["first", "last"]);
    assert_eq!(missing_mitigations.targets, vec!["first", "last"]);
}

#[test]
fn staged_waves_return_empty_when_every_host_is_blocked() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![
            host("old-a", "grub", "x86_64-intel", true, true, "ext4", false, "4.19.0", "audit=1 slab_nomerge intel_iommu=on", vec![]),
            host("boot-b", "systemd-boot", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on", vec![]),
        ],
        policy: RolloutPolicy {
            required_luks_params: vec![],
            ..policy()
        },
    };

    let report = rollout.audit();
    assert_eq!(report.rollout_summary().blocked_hosts, vec!["old-a", "boot-b"]);
    assert!(report.staged_rollout_waves(3).is_empty());
}

#[test]
fn staged_waves_sort_by_warning_count_then_original_order_and_filter_actions() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on debug\"\nGRUB_DISABLE_OS_PROBER=false\n")],
        hosts: vec![
            host("warn-two-a", "grub", "x86_64-intel", true, true, "nfs", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug systemd.log_level=debug", vec![]),
            host("clean-a", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug", vec![]),
            host("blocked-a", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge debug", vec![]),
            host("warn-one-a", "grub", "x86_64-intel", true, true, "tmpfs", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug", vec![]),
            host("clean-b", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug", vec![]),
        ],
        policy: RolloutPolicy {
            forbidden_params: vec![],
            required_luks_params: vec![],
            allowed_debug_params: vec!["debug".to_string()],
            ..policy()
        },
    };

    let waves = rollout.audit().staged_rollout_waves(3);
    assert_eq!(waves.len(), 2);
    assert_eq!(waves[0].hosts, vec!["clean-a", "clean-b", "warn-one-a"]);
    assert_eq!(waves[0].risk_score, 2);
    assert_eq!(waves[0].required_actions, vec![
        "2:os-prober-enabled::global",
        "3:rootfs-risk:tmpfs:warn-one-a",
    ]);
    assert_eq!(waves[1].hosts, vec!["warn-two-a"]);
    assert_eq!(waves[1].risk_score, 3);
    assert_eq!(waves[1].required_actions, vec![
        "2:os-prober-enabled::global",
        "3:debug-param-active:systemd.log_level:warn-two-a",
        "3:rootfs-risk:nfs:warn-two-a",
    ]);
}

#[test]
fn generated_fleet_matrix_exercises_runtime_coverage_and_counting() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on mitigations=auto debug rd.luks.uuid=a rd.luks.options=discard\"\nGRUB_DISABLE_OS_PROBER=true\n")],
        hosts: vec![
            host("clean", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on mitigations=auto debug rd.luks.uuid=a rd.luks.options=discard", vec![]),
            host("audit-drift", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=0 slab_nomerge intel_iommu=on mitigations=auto debug rd.luks.uuid=a rd.luks.options=discard", vec![]),
            host("missing-iommu", "grub", "x86_64-intel", true, true, "nfs", false, "6.2.0", "audit=1 slab_nomerge mitigations=auto debug rd.luks.uuid=a rd.luks.options=discard", vec![]),
            host("missing-mitigations", "grub", "x86_64-intel", true, true, "tmpfs", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug rd.luks.uuid=a rd.luks.options=discard", vec![]),
            host("dup-debug", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on mitigations=auto debug debug rd.luks.uuid=a rd.luks.options=discard", vec![]),
            host("weak-iommu", "grub", "x86_64-intel", true, true, "iscsi", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=pt mitigations=auto debug rd.luks.uuid=a rd.luks.options=discard", vec![]),
        ],
        policy: RolloutPolicy {
            forbidden_params: vec![],
            required_luks_params: vec![],
            allowed_debug_params: vec!["debug".to_string()],
            ..policy()
        },
    };

    let report = rollout.audit();
    assert!(report.global_findings.is_empty());
    assert_eq!(report.hosts[1].blockers, vec!["runtime-value-drift:audit-drift:audit:1:0"]);
    assert_eq!(report.hosts[2].blockers, vec!["runtime-missing-param:missing-iommu:intel_iommu"]);
    assert_eq!(report.hosts[3].blockers, vec!["runtime-missing-param:missing-mitigations:mitigations"]);
    assert_eq!(report.hosts[4].blockers, vec!["runtime-duplicate-param:dup-debug:debug"]);
    assert_eq!(report.hosts[5].blockers, vec![
        "runtime-weak-iommu:weak-iommu:intel_iommu:pt",
        "runtime-value-drift:weak-iommu:intel_iommu:on:pt",
    ]);
    assert_eq!(report.hosts[2].warnings, vec!["rootfs-risk:missing-iommu:nfs"]);
    assert_eq!(report.hosts[3].warnings, vec!["rootfs-risk:missing-mitigations:tmpfs"]);
    assert_eq!(report.hosts[5].warnings, vec!["rootfs-risk:weak-iommu:iscsi"]);

    let summary = report.rollout_summary();
    assert_eq!(summary.blocked_hosts, vec!["audit-drift", "missing-iommu", "missing-mitigations", "dup-debug", "weak-iommu"]);
    assert_eq!(summary.clean_hosts, vec!["clean"]);
    assert_eq!(summary.effective_param_keys, vec!["audit", "slab_nomerge", "intel_iommu", "mitigations", "debug", "rd.luks.uuid", "rd.luks.options"]);
    assert_eq!(summary.required_runtime_coverage.get("audit"), Some(&5));
    assert_eq!(summary.required_runtime_coverage.get("intel_iommu"), Some(&4));
    assert_eq!(summary.required_runtime_coverage.get("mitigations"), Some(&5));
    assert_eq!(summary.required_runtime_coverage.get("debug"), Some(&6));
    assert_eq!(summary.top_finding_codes, vec![
        ("rootfs-risk".to_string(), 3),
        ("runtime-missing-param".to_string(), 2),
        ("runtime-value-drift".to_string(), 2),
        ("runtime-duplicate-param".to_string(), 1),
        ("runtime-weak-iommu".to_string(), 1),
    ]);
}

#[test]
fn generated_remediation_and_wave_matrix_intersect_many_action_types() {
    let rollout = GrubRollout {
        files: vec![file("/etc/default/grub", "GRUB_CMDLINE_LINUX=\"audit=1 slab_nomerge intel_iommu=on debug mitigations=auto\"\nGRUB_DISABLE_OS_PROBER=false\n")],
        hosts: vec![
            host("blocked", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge debug mitigations=auto", vec![]),
            host("clean-a", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug mitigations=auto", vec![]),
            host("warn-debug", "grub", "x86_64-intel", true, true, "ext4", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug mitigations=auto initcall_debug", vec![]),
            host("warn-root", "grub", "x86_64-intel", true, true, "nfs", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug mitigations=auto", vec![]),
            host("warn-both", "grub", "x86_64-intel", true, true, "tmpfs", false, "6.2.0", "audit=1 slab_nomerge intel_iommu=on debug mitigations=auto systemd.log_level=debug", vec![]),
        ],
        policy: RolloutPolicy {
            forbidden_params: vec![],
            required_luks_params: vec![],
            allowed_debug_params: vec!["debug".to_string()],
            ..policy()
        },
    };

    let report = rollout.audit();
    let plan = report.remediation_plan();
    let os_prober = plan.iter().find(|a| a.code == "os-prober-enabled").unwrap();
    assert_eq!(os_prober.targets, vec!["global"]);
    let missing_iommu = plan.iter().find(|a| a.code == "runtime-missing-param" && a.detail == "intel_iommu").unwrap();
    assert_eq!(missing_iommu.targets, vec!["blocked"]);
    let debug_action = plan.iter().find(|a| a.code == "debug-param-active" && a.detail == "initcall_debug").unwrap();
    assert_eq!(debug_action.targets, vec!["warn-debug"]);
    let log_action = plan.iter().find(|a| a.code == "debug-param-active" && a.detail == "systemd.log_level").unwrap();
    assert_eq!(log_action.targets, vec!["warn-both"]);

    let waves = report.staged_rollout_waves(2);
    assert_eq!(waves.len(), 2);
    assert_eq!(waves[0].hosts, vec!["clean-a", "warn-debug"]);
    assert_eq!(waves[0].risk_score, 2);
    assert_eq!(waves[0].required_actions, vec![
        "2:os-prober-enabled::global",
        "3:debug-param-active:initcall_debug:warn-debug",
    ]);
    assert_eq!(waves[1].hosts, vec!["warn-root", "warn-both"]);
    assert_eq!(waves[1].risk_score, 4);
    assert_eq!(waves[1].required_actions, vec![
        "2:os-prober-enabled::global",
        "3:debug-param-active:systemd.log_level:warn-both",
        "3:rootfs-risk:nfs:warn-root",
        "3:rootfs-risk:tmpfs:warn-both",
    ]);
}
'''


def test_rust_contract_tests_pass():
    tests_dir = TASK_DIR / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "hidden_grub_contract.rs").write_text(HIDDEN_TESTS)
    result = subprocess.run(
        ["cargo", "test", "--release", "--locked"],
        cwd=TASK_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout
