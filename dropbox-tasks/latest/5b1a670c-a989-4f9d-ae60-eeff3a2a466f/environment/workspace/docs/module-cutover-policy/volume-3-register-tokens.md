Iris cutover register tokens (IRIS-CUTOVER-2025.06)

The live cutover register named by paths.cutover_register carries opaque policy
tokens. Map each value as follows when walking a proxy export.

replace_match_policy
  list_scan_alpha — scan the unit replaces list from the start; the first
    old_path+old_version match (after +incompatible stripping) wins
  list_scan_omega — scan from the end; the last match wins

checksum_peel_mode
  single_affix — remove one leading h1: or sha256: prefix from unit.checksum
  peel_all — keep removing those prefixes until neither remains at the front

scaffold_gate
  truthy_flags — skip a require only when indirect, toolchain, development, or
    test is JSON true; explicit JSON false still walks
  key_present — skip a require when any of those keys is present at all

queue_timing
  post_rewrite — apply retract_queue and exclude_queue to the child identity
    after replace resolution
  pre_rewrite — apply those queues to the bare require before replace

digest_checksum_layout
  bare_hex_nl — checksum file is sixty-four lowercase hex chars plus one newline
  gnu_sha256sum_line — checksum file is hex, two spaces, then a path (legacy)

Sibling fields such as published_sum on a unit are never the checksum source.
Unused replace rows that never matched an emitted edge stay out of replace_rules.
