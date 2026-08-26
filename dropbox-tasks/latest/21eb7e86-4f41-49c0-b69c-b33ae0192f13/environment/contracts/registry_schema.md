# Bastion access registry (Redis)

The bastion access-control entrypoint reads live Redis state before auditing or remediating staged files.

## Keys

| Key | Type | Content |
|-----|------|---------|
| `bastion:users` | Hash | user id → JSON `{uid, gid, shell, groups[], homedir}` |
| `bastion:ssh_keys` | Hash | user id → single-line OpenSSH public key |
| `bastion:service_accounts` | Set | service account usernames allowed in sudoers |
| `bastion:file_modes` | Hash | relative staging path → octal mode string (e.g. `0700`) |
| `bastion:sshd_settings` | Hash | relative `sshd_config.d` path → JSON map of directive → value |
| `bastion:sudoers_lines` | Hash | rule id → full sudoers line |
| `bastion:overrides:tenant:{tenant}` | Hash | field → JSON blob; tenant leaves win over global hashes when merged |

## Merge

Effective registry merges each `bastion:overrides:tenant:{tenant}` overlay onto the global hashes with **tenant leaves winning** on conflict. Shallow spreads or desk-sheet loading without tenant overlays are incorrect.
