# Cycle witness contract

Graded output path is /app/output/cp_witness.json. Build with /app/environment/scripts/rebuild_bins.sh, drive with /app/environment/scripts/drive_matrix.sh, verify with /app/bin/cp_audit --coverage-audit.

The report carries a cycles array and a summary block. The cycles field reports exactly sixteen entries when drive_matrix completes all profile and pass_mode passes (four profiles times four pass_mode values). Each cycle lists profile_id, pass_mode, band_hex, carry_span, budget_used, and rows with score_hex, cover_hex, nc_skew, lag_code, and slot_id. pass_mode fresh_score means fresh ledger authority, rotate_split means bounce carry republish, trim_holdout means epoch reset with carry wipe, and mirror_restore means tail rebuild without carry wipe. Echo roles lease_echo, worker_echo, and bind_echo mean mirror pair rows for lease, worker, and bind respectively when nc_skew and lag_code converge.

The summary records rows_total, matrix_status, carry_span, and witness_digest.

When drive_matrix completes, per-cycle traces land under /app/output/mode_traces/ and at least sixteen trace files are written for the full profile and mode matrix. The stub_health.json interim_rows array is defined as preview stamps that may look settled before graded score_hex values converge.

Profile schedules live under /app/environment/p3/schedules/ as p3/schedules/xa.json, p3/schedules/xb.json, p3/schedules/xc.json, and p3/schedules/xd.json.
Each schedule carries profile_id, profile_pfx, epoch_dn, epoch_stamp, cap_bytes, frame_unit, grant_unit, and modules with path, version, shard_ref, frame, tomb, role, and echo_role fields.
epoch_dn is defined as tenant anchor DN material embedded in slot_id strings only.
Sum authority lines in /app/environment/c44.txt list 3 whitespace-separated entries when this_up is present.
Section bytes live under /app/environment/fixtures/b5/ including fixtures/b5/f4.bin and fixtures/b5/f5.bin frame slices.
Vendor mirror shard files live under /app/environment/m4/mirrors/ as m4/mirrors/m_a.json, m4/mirrors/m_b.json, and m4/mirrors/m_c.json.

score_hex is defined as sixteen hex digits over issuer, this_up, and sorted serials using sha256 via the same hashlib truncation semantics documented in /app/environment/scripts/carry_seed_guard.py.
The issuer argument is the issuer field from the vendor mirror shard referenced by module shard_ref, not schedule epoch_dn.
this_up resolves from c44.txt authority lines and shard mirror bytes. When a module line or ledger tomb marker is active, the c44.txt this_up wins over stale shard mirror bytes; otherwise the lexicographically larger stable update wins.
Serials are comma-joined in ascending sort order inside the pipe-delimited preimage before hashing.

cover_hex is defined as sixteen hex digits over profile_pfx bytes from the profile schedule immediately concatenated with frame slice bytes from fixtures/b5.
The preimage is raw profile_pfx UTF-8 bytes followed by frame slice bytes with no additional label bytes prepended or interleaved.

slot_id is defined as slab cache slot material with four pipe-separated fields in order module path, module version, schedule epoch_dn, and epoch_stamp with optional mode tagging.
On pass_mode fresh_score the fourth field is schedule epoch_stamp verbatim with no mode suffix.
On rotate_split, trim_holdout, and mirror_restore the fourth field concatenates epoch_stamp, the ASCII colon character (U+003A), and the pass_mode value.
A sample fresh_score slot_id for the lane_amber lease module is the pipe-joined string example.com/alpha|v1.2.1|cn=ca-alpha|20260101.
A sample rotate_split slot_id appends the mode tag after the stamp so the fourth field becomes 20260101 plus colon plus rotate_split.
Values that omit epoch dimensions or mode tagging on non-cold passes leave carry_span nonzero on recovery passes even when a single cold pass looks converged.

nc_skew is defined as numeric distance between echo pair stamp prefixes and reads zero for mirror pairs when converged.
lag_code uses the same distance method for pair agreement.
band_hex is defined as twelve hex digits over sorted row score_hex values.
carry_span is defined as cap_bytes minus consumed slab and pin bytes for the lane pass.
budget_used is defined as new slab slots times frame_unit plus row count times grant_unit for that pass.
witness_digest is defined as sixteen hex digits over a sha256 preimage built from sorted cycle tuples.
Sort tuples by profile_id then pass_mode.
Each tuple is profile_id, pass_mode, band_hex, and carry_span joined with ASCII colon characters in that order.
Join the sorted tuple strings with pipe characters only between tuples, not between fields within a tuple.
A sample lane_amber fresh_score tuple string is lane_amber plus colon plus fresh_score plus colon plus af392321e9c1 plus colon plus 0.
The settled witness_digest for the anchored tenant matrix is a3c72576b03c179f. The sixteen-cycle preimage that hashes to that digest is produced by sorting all cycle tuples then pipe-joining them as described above.
matrix_status reads settled when every cycle carry_span meets the contract threshold and every row nc_skew meets the contract threshold.
The anchored matrix expands to 96 total rows across sixteen passes (six modules per profile times four profiles times four pass modes divided across cycles yields rows_total 96).

After cache reset, run `bash /app/environment/migrations/cln8.sh --apply /app/environment/fixtures/seed/cp_seed.bin` before rerun.

When ledger lines carry tomb markers, the durable sum update line wins over stale vendor mirror bytes.

Partial evidence lives in /app/environment/fixtures/logs/gt_tail.txt and gt_tail is defined as a truncated ledger tail that may omit carry state.
