use bootlineguard::*;

#[test]
fn smoke_audit_keeps_host_order() {
    let rollout = GrubRollout {
        files: vec![],
        hosts: vec![HostState {
            hostname: "host-a".to_string(),
            bootloader: "grub".to_string(),
            arch: "x86_64-intel".to_string(),
            secure_boot: false,
            lockdown: false,
            tpm2: false,
            root_fs: "ext4".to_string(),
            encrypted_root: false,
            kernel_version: "6.1.0".to_string(),
            cmdline_runtime: String::new(),
            modules: vec![],
        }],
        policy: RolloutPolicy {
            min_kernel_version: "5.15.0".to_string(),
            require_secure_boot: false,
            require_lockdown: false,
            require_iommu: false,
            forbidden_params: vec![],
            required_params: vec![],
            allowed_debug_params: vec![],
            required_luks_params: vec![],
        },
    };

    let report = rollout.audit();
    assert_eq!(report.hosts[0].hostname, "host-a");
}
