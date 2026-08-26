Draft normalize notes (2024.11 loader)

The draft loader wired against archive-cutover-register.json used
list_scan_omega, peel_all, key_present, pre_rewrite, and gnu_sha256sum_line. It
also dumped shadow_index entries, preferred published_sum and unit go_version,
took units[0] regardless of path, collapsed versions with MVS, matched replace
by path alone, copied every replaces row into replace_rules, preferred
legacy_proxy_export / database_path when present, always ran Phinx against the
checked-in phinx.php adapter, and labeled digest lines kind replace_rule with
integer is_root fields.

The Composer package under /workspace/iris-provenance still mirrors that draft
wiring until cutover IRIS-CUTOVER-2025.06 is applied from the live register.
