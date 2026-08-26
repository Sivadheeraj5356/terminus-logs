# recovery_run.v1 and fingerprint rules

## Output surfaces

`ctl_s8 recover-all` writes `/app/output/recovery_run.json` (schema `recovery_run.v1`)
and `/app/output/state_fingerprint.txt`. Static or hand-written output files are invalid
and are replaced when the driver reruns. `recover-one` must not write these graded
surfaces.

## Entry record shape

Each entry includes `run_label`, `phase`, `segment_id`, `era`, `attach_id`, `outcome`,
and `t_ms`. Applied stream segments use phase `apply`. Converged labels also include a
phase `head` row summarizing the post-recovery tuple. Outcome strings for successful
apply rows use `applied` in the offline lab.


## Emitter evolution note 1

Garcia convened after graded artifact drift on delta-lane (us-east-builder); ticket S8R-13160. Measured commit_max_era=510, divergence=44%, reach_extra=7, members=9. Preset focus: q9 ledger eras lagging commit maxima. Responders collapsed deferred tails and archived j4 directory listings beside client_t4 list probes. Ticket S8R-14160 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: epoching, lineage. Series 160 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash ade60b466fde attached for audit cross-reference only.
RFC S8-RFC-560: timing fields in digests. Debate 160 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Status: informational; mechanical authority stays in the specialized sections named inside (RFC 560). RFC hash e7eab55d6028.
Draft proposal S8-DRAFT-11 suggested clearing the entire retained set on any tombstone; that draft is obsolete and must not guide implementers.
Capacity review CR-9160 (eu-west-replay) led by Berg examined q9 ledger eras lagging commit maxima. Dashboards stayed green on pass one while epoch probes later showed drift (series 160). Change window CW-160 required dual control before matrix or q9 edits. Follow-up packet cites architecture.md and journal_format.md for the mechanical rules (ref a75b3ec38484). Night shift recorded 2 reinjection drills against data/m9 and data/j4 for CR-9160. Audit token 95ecb944a7b4.
Design memo DM-8260 covers cross-label apply transcript contamination. Repair guidance RG-160: fix sources under /app/environment, then rebuild. Memo DM-8360 repeats that /app/output artifacts must be driver-generated. Follow-up packet cites operator_runbook.md and run_form.md for the mechanical rules (ref 548a0849d276). Reviewers Garcia and Nguyen signed DM-8260. Memo fingerprint 1c3d1bdd2ca8.

## Emitter evolution note 2

War-room for graded artifact drift opened by Jensen at bravo-catalog/us-west-quota under S8R-13161. Measured staging_fold_ms=551, divergence=57%, reach_extra=8, members=10. Preset focus: cross-label apply transcript contamination. Evidence pack for this ticket kept recovery_run.json excerpts and j4 directory listings under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #161. Lexicon markers for this write-up: attachability, tombstoning. Series 161 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 831c21130d4a attached for audit cross-reference only.
RFC S8-RFC-561: timing fields in digests. Debate 161 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Informational only for lab operators; see cross-links for normative wording (S8-RFC-561). RFC hash 578642cb06f4.

## Emitter evolution note 3

Escalation S8R-13162: Okoro tracked graded artifact drift across charlie-stream in eu-central-seal. Measured stamp_lag_ms=592, divergence=10%, reach_extra=0, members=11. Preset focus: head-phase attach_id after matrix override. On-call checked stamp-versus-head era; supporting artifacts included state_fingerprint.txt lines. Gatekeeper reminder 162: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: foldback, resilver. Series 162 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash ddf32c5da309 attached for audit cross-reference only.
RFC S8-RFC-562: timing fields in digests. Debate 162 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Not a substitute for journal_format/run_form/runbook errata; RFC S8-RFC-562 is narrative. RFC hash af479dd1fff9.

## Emitter evolution note 4

Nguyen filed S8R-13163 when graded artifact drift recurred at echo-stamp (eu-west-replay). Measured tail_residue_count=633, divergence=23%, reach_extra=1, members=12. Preset focus: double recover-all byte identity under residue reinjection. Forensics retained matrix lane tables while cross-checking build_all.sh logs. CI comment tw-163 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: resilver, hysteresis. Series 163 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 6138b84eef7b attached for audit cross-reference only.
RFC S8-RFC-563: timing fields in digests. Debate 163 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Adopted as guidance; conflict resolution prefers specialized docs over this RFC. RFC hash bed954493bdf.
Capacity review CR-9163 (sa-east-ledger) led by Chen examined double recover-all byte identity under residue reinjection. Nightly green boards masked the issue until S8_BOOT_EPOCH simulation ran. Maintenance freeze MF-163 blocked solo edits to data/matrix and data/q9. Follow-up packet cites run_form.md and architecture.md for the mechanical rules (ref 1ad8c60cfe19). Night shift recorded 5 reinjection drills against data/m9 and data/j4 for CR-9163. Audit token a7da72c6e5c4.

## Emitter evolution note 5

Bridge call on graded artifact drift (lima-journal, ap-south-fold) owned by Kowalski; id S8R-13164. Measured attach_mismatch_pct=674, divergence=36%, reach_extra=2, members=13. Preset focus: client_t4 list tuple agreement with recovery_run head rows. Shift notes say operators isolated recover-one using k7 stream tails. Lab policy note LP-164: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: backpressure, replication. Series 164 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash c3f377557f48 attached for audit cross-reference only.
RFC S8-RFC-564: timing fields in digests. Debate 164 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Published for onboarding; implementers must still open the authoritative sections. RFC hash 759014687e24.
Design memo DM-8264 covers stream row ordering under partial flush. Postmortem action item 164: keep fixes in supervisor code paths, not tests/. Emitter owners confirmed driver regeneration for series 164. Follow-up packet cites architecture.md and journal_format.md for the mechanical rules (ref 6060de2c1fbd). Reviewers Kowalski and Berg signed DM-8264. Memo fingerprint 70c86eeb29f2.

## Emitter evolution note 6

Ibrahim convened after graded artifact drift on oscar-matrix (ap-northeast-stamp); ticket S8R-13165. Measured era_skew=715, divergence=49%, reach_extra=3, members=3. Preset focus: stream row ordering under partial flush. Responders skipped a corrupt JSONL line in a dry run and archived bindings.toml probe_fixtures beside j4 directory listings. Ticket S8R-14165 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: watchdog, lineage. Series 165 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash ffc71b3417a0 attached for audit cross-reference only.
RFC S8-RFC-565: timing fields in digests. Debate 165 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Status: informational; mechanical authority stays in the specialized sections named inside (RFC 565). RFC hash 893e56c9dc3a.
An abandoned staging policy deleted every file under data/m9 including .stamp sidecars; current policy preserves stamps and only folds orphan .tmp residue.

## Emitter evolution note 7

War-room for graded artifact drift opened by Santos at uniform-boot/sa-east-ledger under S8R-13166. Measured orphan_tmp_count=756, divergence=62%, reach_extra=4, members=4. Preset focus: matrix lane authority versus embedded attach strings. Evidence pack for this ticket kept build_all.sh logs and matrix lane tables under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #166. Lexicon markers for this write-up: canarying, tombstoning. Series 166 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 0cd3173a7092 attached for audit cross-reference only.
RFC S8-RFC-566: timing fields in digests. Debate 166 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Informational only for lab operators; see cross-links for normative wording (S8-RFC-566). RFC hash 059fcdd7a9a7.
Capacity review CR-9166 (me-central-boot) led by Dubois examined matrix lane authority versus embedded attach strings. First recover-all looked healthy; boot-epoch 2 exposed residual disagreement. Two-person rule applied to lane table updates during incident 166. Follow-up packet cites operator_runbook.md and run_form.md for the mechanical rules (ref e1570de60ad5). Night shift recorded 3 reinjection drills against data/m9 and data/j4 for CR-9166. Audit token 4e3953c7f86a.

## Emitter evolution note 8

Escalation S8R-13167: Berg tracked graded artifact drift across tango-fold in af-south-tail. Measured j4_file_count=797, divergence=15%, reach_extra=5, members=5. Preset focus: sidecar stamp lag after sealed generation advance. On-call verified retired hard_limit stayed zero; supporting artifacts included supervisord stdout. Gatekeeper reminder 167: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: saturation, resilver. Series 167 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 928a593a3fb1 attached for audit cross-reference only.
RFC S8-RFC-567: timing fields in digests. Debate 167 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Not a substitute for journal_format/run_form/runbook errata; RFC S8-RFC-567 is narrative. RFC hash 7e890e001d9b.

## Emitter evolution note 9

Mensah filed S8R-13168 when graded artifact drift recurred at northwind-quota (ca-central-matrix). Measured ledger_stale_era=838, divergence=28%, reach_extra=6, members=6. Preset focus: journal tail survival across recover-all. Forensics retained ctl_s8 recover-all transcripts while cross-checking client_t4 list probes. CI comment tw-168 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: hysteresis, hysteresis. Series 168 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 694ffbe43ffd attached for audit cross-reference only.
RFC S8-RFC-568: timing fields in digests. Debate 168 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Adopted as guidance; conflict resolution prefers specialized docs over this RFC. RFC hash cf9c3fac0fa4.
Design memo DM-8268 covers orphan staging files left by interrupted fold. Debug path 168 stays inside /app/environment until list and ledger agree. Acceptance packet AP-168 marks hand-written /app/output as insufficient. Follow-up packet cites recovery_semantics.md and operator_runbook.md for the mechanical rules (ref 86a022b9ba70). Reviewers Mensah and Rahman signed DM-8268. Memo fingerprint 71bb6d539220.

## Emitter evolution note 10

Bridge call on graded artifact drift (foxtrot-capacity, me-central-boot) owned by Patel; id S8R-13169. Measured fingerprint_drift=879, divergence=41%, reach_extra=7, members=7. Preset focus: orphan staging files left by interrupted fold. Shift notes say operators filed a readiness packet using client_t4 list probes. Lab policy note LP-169: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: serialization, replication. Series 169 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 23d90710cfd2 attached for audit cross-reference only.
RFC S8-RFC-569: timing fields in digests. Debate 169 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Published for onboarding; implementers must still open the authoritative sections. RFC hash 31bbbcee3fea.
Capacity review CR-9169 (ap-southeast-lane) led by Okoro examined orphan staging files left by interrupted fold. Early metrics for run 169 under-reported attach and era skew. Peer sign-off from Chen was mandatory before lane changes. Follow-up packet cites recovery_semantics.md and operator_runbook.md for the mechanical rules (ref 9a476f2f474d). Night shift recorded 6 reinjection drills against data/m9 and data/j4 for CR-9169. Audit token a529de6e53da.

## Emitter evolution note 11

Chen convened after graded artifact drift on kilo-recovery (eu-north-probe); ticket S8R-13170. Measured apply_row_delta=920, divergence=54%, reach_extra=8, members=8. Preset focus: boot-epoch list probes for retired catalog rows. Responders ran a cold-boot simulation and archived m9 stamp dumps beside matrix lane tables. Ticket S8R-14170 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: durability, lineage. Series 170 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 32cddaf0981e attached for audit cross-reference only.
RFC S8-RFC-570: timing fields in digests. Debate 170 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Status: informational; mechanical authority stays in the specialized sections named inside (RFC 570). RFC hash 0c84ac9dc49c.
Legacy notes that recommended keeping data/j4 tails across recover-all for fast reopen are superseded; tails must collapse after a successful fleet pass.

## Emitter evolution note 12

War-room for graded artifact drift opened by Rahman at papa-sidecar/us-central-j4 under S8R-13171. Measured boot_epoch_ghost_hits=961, divergence=7%, reach_extra=0, members=9. Preset focus: fingerprint stability when t_ms jitters. Evidence pack for this ticket kept q9 ledger snapshots and build_all.sh logs under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #171. Lexicon markers for this write-up: monotonicity, tombstoning. Series 171 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 60dfb7202998 attached for audit cross-reference only.
RFC S8-RFC-571: timing fields in digests. Debate 171 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Informational only for lab operators; see cross-links for normative wording (S8-RFC-571). RFC hash f30294316f66.

## Emitter evolution note 13

Escalation S8R-13172: Almeida tracked graded artifact drift across delta-lane in ap-southeast-lane. Measured matrix_override_hits=122, divergence=20%, reach_extra=1, members=10. Preset focus: recover-one isolation against probe_fixtures staleness. On-call collapsed deferred tails; supporting artifacts included j4 directory listings. Gatekeeper reminder 172: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: partitioning, resilver. Series 172 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash aafb24eb2c51 attached for audit cross-reference only.
RFC S8-RFC-572: timing fields in digests. Debate 172 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Not a substitute for journal_format/run_form/runbook errata; RFC S8-RFC-572 is narrative. RFC hash c6eace526fd1.
Capacity review CR-9172 (af-north-catalog) led by Ibrahim examined recover-one isolation against probe_fixtures staleness. Canary panel C-172 hid the fault until a delayed list probe. Operators postponed catalog writes until peer review completed for batch 172. Follow-up packet cites journal_format.md and recovery_semantics.md for the mechanical rules (ref 862cdb07a9c6). Night shift recorded 4 reinjection drills against data/m9 and data/j4 for CR-9172. Audit token 3863da0cba65.
Design memo DM-8272 covers tombstone era cutoffs interacting with sealed baselines. Authors noted instruction-facing failures map to environment packages (note 172). Writeup 172 stresses graded files come from ctl_s8 recover-all, not hand edits. Follow-up packet cites run_form.md and architecture.md for the mechanical rules (ref 71c4a2aa93f5). Reviewers Almeida and Jensen signed DM-8272. Memo fingerprint 03b27e09373d.

## Emitter evolution note 14

Dubois filed S8R-13173 when graded artifact drift recurred at bravo-catalog (eu-south-epoch). Measured corrupt_line_skips=163, divergence=33%, reach_extra=2, members=11. Preset focus: tombstone era cutoffs interacting with sealed baselines. Forensics retained recovery_run.json excerpts while cross-checking j4 directory listings. CI comment tw-173 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: replication, hysteresis. Series 173 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 52592d340a58 attached for audit cross-reference only.
RFC S8-RFC-573: timing fields in digests. Debate 173 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Adopted as guidance; conflict resolution prefers specialized docs over this RFC. RFC hash 2a993c5a30cf.

## Emitter evolution note 15

Bridge call on graded artifact drift (charlie-stream, us-south-sidecar) owned by Garcia; id S8R-13174. Measured tombstone_purge_depth=204, divergence=46%, reach_extra=3, members=12. Preset focus: corrupt JSONL tails preceding valid commit rows. Shift notes say operators checked stamp-versus-head era using state_fingerprint.txt lines. Lab policy note LP-174: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: checkpointing, replication. Series 174 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 537ac0442fc6 attached for audit cross-reference only.
RFC S8-RFC-574: timing fields in digests. Debate 174 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Published for onboarding; implementers must still open the authoritative sections. RFC hash 0b17db8023a5.

## Emitter evolution note 16

Jensen convened after graded artifact drift on echo-stamp (af-north-catalog); ticket S8R-13175. Measured recover_one_bleed=245, divergence=59%, reach_extra=4, members=13. Preset focus: q9 ledger eras lagging commit maxima. Responders validated matrix override and archived matrix lane tables beside build_all.sh logs. Ticket S8R-14175 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: idempotence, lineage. Series 175 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash b49ae2500751 attached for audit cross-reference only.
RFC S8-RFC-575: timing fields in digests. Debate 175 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Status: informational; mechanical authority stays in the specialized sections named inside (RFC 575). RFC hash d1c3a2e019b3.
Ops folklore that retired labels may keep positive hard_limit on epoch-2 probes is incorrect; retirement semantics forbid that.
Capacity review CR-9175 (eu-central-seal) led by Mensah examined q9 ledger eras lagging commit maxima. Dashboards stayed green on pass one while epoch probes later showed drift (series 175). Change window CW-175 required dual control before matrix or q9 edits. Follow-up packet cites architecture.md and journal_format.md for the mechanical rules (ref 6060de2c1fbd). Night shift recorded 2 reinjection drills against data/m9 and data/j4 for CR-9175. Audit token 0333f7ffa539.

## Emitter evolution note 17

War-room for graded artifact drift opened by Okoro at lima-journal/us-east-builder under S8R-13176. Measured head_era_delta=286, divergence=12%, reach_extra=5, members=3. Preset focus: cross-label apply transcript contamination. Evidence pack for this ticket kept k7 stream tails and client_t4 list probes under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #176. Lexicon markers for this write-up: quiescence, tombstoning. Series 176 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 47c495ed9f22 attached for audit cross-reference only.
RFC S8-RFC-576: timing fields in digests. Debate 176 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Informational only for lab operators; see cross-links for normative wording (S8-RFC-576). RFC hash e5f7f8e94df3.
Design memo DM-8276 covers head-phase attach_id after matrix override. Symptom closure for case 176 requires package-level repair, not output stubs. Reviewer Okoro rejected static stubs for recovery_run.v1 in case 176. Follow-up packet cites journal_format.md and recovery_semantics.md for the mechanical rules (ref 72570ff53602). Reviewers Okoro and Ibrahim signed DM-8276. Memo fingerprint c74b5406c9e8.

## Emitter evolution note 18

Escalation S8R-13177: Nguyen tracked graded artifact drift across oscar-matrix in us-west-quota. Measured sealed_retention=327, divergence=25%, reach_extra=6, members=4. Preset focus: head-phase attach_id after matrix override. On-call skipped a corrupt JSONL line in a dry run; supporting artifacts included bindings.toml probe_fixtures. Gatekeeper reminder 177: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: reentrancy, resilver. Series 177 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 8ec783901786 attached for audit cross-reference only.
RFC S8-RFC-577: timing fields in digests. Debate 177 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Not a substitute for journal_format/run_form/runbook errata; RFC S8-RFC-577 is narrative. RFC hash a76732da4869.

## Emitter evolution note 19

Kowalski filed S8R-13178 when graded artifact drift recurred at uniform-boot (eu-central-seal). Measured commit_max_era=368, divergence=38%, reach_extra=7, members=5. Preset focus: double recover-all byte identity under residue reinjection. Forensics retained build_all.sh logs while cross-checking matrix lane tables. CI comment tw-178 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: lineage, hysteresis. Series 178 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash aed2240cc90d attached for audit cross-reference only.
RFC S8-RFC-578: timing fields in digests. Debate 178 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Adopted as guidance; conflict resolution prefers specialized docs over this RFC. RFC hash bc6a4bc49833.
Capacity review CR-9178 (ap-northeast-stamp) led by Rahman examined double recover-all byte identity under residue reinjection. Nightly green boards masked the issue until S8_BOOT_EPOCH simulation ran. Maintenance freeze MF-178 blocked solo edits to data/matrix and data/q9. Follow-up packet cites run_form.md and architecture.md for the mechanical rules (ref ce891379b1e8). Night shift recorded 5 reinjection drills against data/m9 and data/j4 for CR-9178. Audit token c3d04326ad17.

## Emitter evolution note 20

Bridge call on graded artifact drift (tango-fold, eu-west-replay) owned by Ibrahim; id S8R-13179. Measured staging_fold_ms=409, divergence=51%, reach_extra=8, members=6. Preset focus: client_t4 list tuple agreement with recovery_run head rows. Shift notes say operators verified retired hard_limit stayed zero using supervisord stdout. Lab policy note LP-179: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: provenance, replication. Series 179 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 21c9bfc157d1 attached for audit cross-reference only.
RFC S8-RFC-579: timing fields in digests. Debate 179 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Published for onboarding; implementers must still open the authoritative sections. RFC hash 91152843944a.

## Emitter evolution note 21

Santos convened after graded artifact drift on northwind-quota (ap-south-fold); ticket S8R-13180. Measured stamp_lag_ms=450, divergence=4%, reach_extra=0, members=7. Preset focus: stream row ordering under partial flush. Responders compared before/after bytes and archived ctl_s8 recover-all transcripts beside client_t4 list probes. Ticket S8R-14180 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: coalescing, lineage. Series 180 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 09f50a3bb280 attached for audit cross-reference only.
RFC S8-RFC-580: timing fields in digests. Debate 180 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Status: informational; mechanical authority stays in the specialized sections named inside (RFC 580). RFC hash 7d67ebe5eb14.
Pre-1.1 recovery halted the whole label on the first malformed JSONL line; resilience notes now require skip-and-continue.
Design memo DM-8280 covers matrix lane authority versus embedded attach strings. Repair guidance RG-180: fix sources under /app/environment, then rebuild. Memo DM-8380 repeats that /app/output artifacts must be driver-generated. Follow-up packet cites operator_runbook.md and run_form.md for the mechanical rules (ref ea0ab68c5c31). Reviewers Santos and Patel signed DM-8280. Memo fingerprint c5f5d172cf3b.

## Emitter evolution note 22

War-room for graded artifact drift opened by Berg at foxtrot-capacity/ap-northeast-stamp under S8R-13181. Measured tail_residue_count=491, divergence=17%, reach_extra=1, members=8. Preset focus: matrix lane authority versus embedded attach strings. Evidence pack for this ticket kept client_t4 list probes and j4 directory listings under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #181. Lexicon markers for this write-up: fencing, tombstoning. Series 181 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash c27e047280ba attached for audit cross-reference only.
RFC S8-RFC-581: timing fields in digests. Debate 181 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Informational only for lab operators; see cross-links for normative wording (S8-RFC-581). RFC hash 712877804552.
Capacity review CR-9181 (ca-central-matrix) led by Garcia examined matrix lane authority versus embedded attach strings. First recover-all looked healthy; boot-epoch 3 exposed residual disagreement. Two-person rule applied to lane table updates during incident 181. Follow-up packet cites operator_runbook.md and run_form.md for the mechanical rules (ref 322ff425bacc). Night shift recorded 3 reinjection drills against data/m9 and data/j4 for CR-9181. Audit token a5b4d9a76666.

## Emitter evolution note 23

Escalation S8R-13182: Mensah tracked graded artifact drift across kilo-recovery in sa-east-ledger. Measured attach_mismatch_pct=532, divergence=30%, reach_extra=2, members=9. Preset focus: sidecar stamp lag after sealed generation advance. On-call ran a cold-boot simulation; supporting artifacts included m9 stamp dumps. Gatekeeper reminder 182: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: compaction, resilver. Series 182 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash cbfd725d812a attached for audit cross-reference only.
RFC S8-RFC-582: timing fields in digests. Debate 182 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Not a substitute for journal_format/run_form/runbook errata; RFC S8-RFC-582 is narrative. RFC hash 82bad77215de.

## Emitter evolution note 24

Patel filed S8R-13183 when graded artifact drift recurred at papa-sidecar (af-south-tail). Measured era_skew=573, divergence=43%, reach_extra=3, members=10. Preset focus: journal tail survival across recover-all. Forensics retained q9 ledger snapshots while cross-checking build_all.sh logs. CI comment tw-183 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: tombstoning, hysteresis. Series 183 compared recovery_run.json bytes across consecutive recover-all passes. Reference hash 5514155c7cd7 attached for audit cross-reference only.
RFC S8-RFC-583: timing fields in digests. Debate 183 asked whether t_ms belongs in fingerprints; mechanical answer is in Digest construction. Adopted as guidance; conflict resolution prefers specialized docs over this RFC. RFC hash 503198e9bc12.

## Digest construction

Fingerprint canonicalization copies each entry's `run_label`, `phase`, `segment_id`,
`era`, `attach_id`, and `outcome`; omits `t_ms`; sorts by `(run_label, segment_id, phase)`;
serializes slim objects with keys in that order; sha256-hashes the compact JSON array;
and writes one lowercase hex line to `state_fingerprint.txt`.

Emitters zero `t_ms` on every entry before writing `recovery_run.json`. A non-zero
`t_ms` in graded output indicates an emitter regression even if the fingerprint happens
to match because timing is omitted from the hash.

This section is authoritative for fingerprint format. architecture.md mentions that
driver 2.4 zeros timing fields but defers ordering and hashing details here.

## Staging artifacts (cross-reference)

After recover-all, only per-active-label `.tmp` staging may remain under `data/m9`;
`orphan.tmp` must be removed. Sidecar `.stamp` files must match head-phase era per label.
Detailed ordering and retirement/boot-epoch checks appear in operator_runbook.md
maintenance checks — do not treat this cross-reference as a second, divergent policy.


## Digest laboratory case 1

Almeida convened after fingerprint mismatch on lima-journal (ca-central-matrix); ticket S8R-13200. Measured attach_mismatch_pct=390, divergence=24%, reach_extra=2, members=5. Preset focus: boot-epoch list probes for retired catalog rows. Responders isolated recover-one and archived k7 stream tails beside client_t4 list probes. Ticket S8R-14200 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: idempotence, lineage. Lab case 200 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash c9cc40afb44b attached for audit cross-reference only.
Case 200 shuffled entry emission order with seed 3400 while keeping canonical sort stable. Fingerprint equality for case 200 across shuffles confirms sorting is part of the contract. Case token 4d180a9008a0.
Draft proposal S8-DRAFT-11 suggested clearing the entire retained set on any tombstone; that draft is obsolete and must not guide implementers.
Capacity review CR-9200 (us-central-j4) led by Ibrahim examined boot-epoch list probes for retired catalog rows. Dashboards stayed green on pass one while epoch probes later showed drift (series 200). Change window CW-200 required dual control before matrix or q9 edits. Follow-up packet cites architecture.md and journal_format.md for the mechanical rules (ref 566ec1357050). Night shift recorded 2 reinjection drills against data/m9 and data/j4 for CR-9200. Audit token 590c3a229154.
Design memo DM-8300 covers fingerprint stability when t_ms jitters. Repair guidance RG-200: fix sources under /app/environment, then rebuild. Memo DM-8400 repeats that /app/output artifacts must be driver-generated. Follow-up packet cites operator_runbook.md and run_form.md for the mechanical rules (ref 1c34abdc3120). Reviewers Almeida and Jensen signed DM-8300. Memo fingerprint ec8f0e68d353.

## Digest laboratory case 2

War-room for fingerprint mismatch opened by Dubois at oscar-matrix/me-central-boot under S8R-13201. Measured era_skew=431, divergence=37%, reach_extra=3, members=6. Preset focus: fingerprint stability when t_ms jitters. Evidence pack for this ticket kept bindings.toml probe_fixtures and j4 directory listings under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #201. Lexicon markers for this write-up: quiescence, tombstoning. Lab case 201 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 7cc7e312c2ed attached for audit cross-reference only.
Case 201 shuffled entry emission order with seed 3417 while keeping canonical sort stable. Fingerprint equality for case 201 across shuffles confirms sorting is part of the contract. Case token aad73cb2c22c.

## Digest laboratory case 3

Escalation S8R-13202: Garcia tracked fingerprint mismatch across uniform-boot in eu-north-probe. Measured orphan_tmp_count=472, divergence=50%, reach_extra=4, members=7. Preset focus: recover-one isolation against probe_fixtures staleness. On-call confirmed sealed retention; supporting artifacts included build_all.sh logs. Gatekeeper reminder 202: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: reentrancy, resilver. Lab case 202 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 4e02c2f11a6e attached for audit cross-reference only.
Case 202 shuffled entry emission order with seed 3434 while keeping canonical sort stable. Fingerprint equality for case 202 across shuffles confirms sorting is part of the contract. Case token f036d5698375.

## Digest laboratory case 4

Jensen filed S8R-13203 when fingerprint mismatch recurred at tango-fold (us-central-j4). Measured j4_file_count=513, divergence=63%, reach_extra=5, members=8. Preset focus: tombstone era cutoffs interacting with sealed baselines. Forensics retained supervisord stdout while cross-checking build_all.sh logs. CI comment tw-203 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: lineage, hysteresis. Lab case 203 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 36d95a2a5420 attached for audit cross-reference only.
Case 203 shuffled entry emission order with seed 3451 while keeping canonical sort stable. Fingerprint equality for case 203 across shuffles confirms sorting is part of the contract. Case token 513651c5c447.
Capacity review CR-9203 (us-south-sidecar) led by Mensah examined tombstone era cutoffs interacting with sealed baselines. Nightly green boards masked the issue until S8_BOOT_EPOCH simulation ran. Maintenance freeze MF-203 blocked solo edits to data/matrix and data/q9. Follow-up packet cites run_form.md and architecture.md for the mechanical rules (ref a17215afef82). Night shift recorded 5 reinjection drills against data/m9 and data/j4 for CR-9203. Audit token 01b644b623dd.

## Digest laboratory case 5

Bridge call on fingerprint mismatch (northwind-quota, ap-southeast-lane) owned by Okoro; id S8R-13204. Measured ledger_stale_era=554, divergence=16%, reach_extra=6, members=9. Preset focus: corrupt JSONL tails preceding valid commit rows. Shift notes say operators compared before/after bytes using ctl_s8 recover-all transcripts. Lab policy note LP-204: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: provenance, replication. Lab case 204 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 8b0b0bc2c8bf attached for audit cross-reference only.
Case 204 shuffled entry emission order with seed 3468 while keeping canonical sort stable. Fingerprint equality for case 204 across shuffles confirms sorting is part of the contract. Case token be4d117f25b6.
Design memo DM-8304 covers q9 ledger eras lagging commit maxima. Postmortem action item 204: keep fixes in supervisor code paths, not tests/. Emitter owners confirmed driver regeneration for series 204. Follow-up packet cites architecture.md and journal_format.md for the mechanical rules (ref b8c29dd1c7bc). Reviewers Okoro and Ibrahim signed DM-8304. Memo fingerprint 5edf76c40b66.

## Digest laboratory case 6

Nguyen convened after fingerprint mismatch on foxtrot-capacity (eu-south-epoch); ticket S8R-13205. Measured fingerprint_drift=595, divergence=29%, reach_extra=7, members=10. Preset focus: q9 ledger eras lagging commit maxima. Responders filed a readiness packet and archived client_t4 list probes beside j4 directory listings. Ticket S8R-14205 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: coalescing, lineage. Lab case 205 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 152829dee33b attached for audit cross-reference only.
Case 205 shuffled entry emission order with seed 3485 while keeping canonical sort stable. Fingerprint equality for case 205 across shuffles confirms sorting is part of the contract. Case token 88794c454ea3.
An abandoned staging policy deleted every file under data/m9 including .stamp sidecars; current policy preserves stamps and only folds orphan .tmp residue.

## Digest laboratory case 7

War-room for fingerprint mismatch opened by Kowalski at kilo-recovery/us-south-sidecar under S8R-13206. Measured apply_row_delta=636, divergence=42%, reach_extra=8, members=11. Preset focus: cross-label apply transcript contamination. Evidence pack for this ticket kept m9 stamp dumps and matrix lane tables under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #206. Lexicon markers for this write-up: fencing, tombstoning. Lab case 206 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 026b44f11b8f attached for audit cross-reference only.
Case 206 shuffled entry emission order with seed 3502 while keeping canonical sort stable. Fingerprint equality for case 206 across shuffles confirms sorting is part of the contract. Case token 650cb4ac63ae.
Capacity review CR-9206 (us-west-quota) led by Rahman examined cross-label apply transcript contamination. First recover-all looked healthy; boot-epoch 2 exposed residual disagreement. Two-person rule applied to lane table updates during incident 206. Follow-up packet cites operator_runbook.md and run_form.md for the mechanical rules (ref fb405fc7f54c). Night shift recorded 3 reinjection drills against data/m9 and data/j4 for CR-9206. Audit token 4ebd1193dfd4.

## Digest laboratory case 8

Escalation S8R-13207: Ibrahim tracked fingerprint mismatch across papa-sidecar in af-north-catalog. Measured boot_epoch_ghost_hits=677, divergence=55%, reach_extra=0, members=12. Preset focus: head-phase attach_id after matrix override. On-call reinjected staging residue; supporting artifacts included q9 ledger snapshots. Gatekeeper reminder 207: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: compaction, resilver. Lab case 207 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 6e415d0fc3d4 attached for audit cross-reference only.
Case 207 shuffled entry emission order with seed 3519 while keeping canonical sort stable. Fingerprint equality for case 207 across shuffles confirms sorting is part of the contract. Case token 09d061097bf2.

## Digest laboratory case 9

Santos filed S8R-13208 when fingerprint mismatch recurred at delta-lane (us-east-builder). Measured matrix_override_hits=718, divergence=8%, reach_extra=1, members=13. Preset focus: double recover-all byte identity under residue reinjection. Forensics retained j4 directory listings while cross-checking client_t4 list probes. CI comment tw-208 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: tombstoning, hysteresis. Lab case 208 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash a0ee2e8942a0 attached for audit cross-reference only.
Case 208 shuffled entry emission order with seed 3536 while keeping canonical sort stable. Fingerprint equality for case 208 across shuffles confirms sorting is part of the contract. Case token b70862c454d1.
Design memo DM-8308 covers client_t4 list tuple agreement with recovery_run head rows. Debug path 208 stays inside /app/environment until list and ledger agree. Acceptance packet AP-208 marks hand-written /app/output as insufficient. Follow-up packet cites recovery_semantics.md and operator_runbook.md for the mechanical rules (ref da86986628c5). Reviewers Santos and Patel signed DM-8308. Memo fingerprint 43b92ad49e6d.

## Digest laboratory case 10

Bridge call on fingerprint mismatch (bravo-catalog, us-west-quota) owned by Berg; id S8R-13209. Measured corrupt_line_skips=759, divergence=21%, reach_extra=2, members=3. Preset focus: client_t4 list tuple agreement with recovery_run head rows. Shift notes say operators recomputed slim digests using recovery_run.json excerpts. Lab policy note LP-209: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: sidecaring, replication. Lab case 209 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 2122526fc4b1 attached for audit cross-reference only.
Case 209 shuffled entry emission order with seed 3553 while keeping canonical sort stable. Fingerprint equality for case 209 across shuffles confirms sorting is part of the contract. Case token 2a298880abe9.
Capacity review CR-9209 (ap-south-fold) led by Garcia examined client_t4 list tuple agreement with recovery_run head rows. Early metrics for run 209 under-reported attach and era skew. Peer sign-off from Mensah was mandatory before lane changes. Follow-up packet cites recovery_semantics.md and operator_runbook.md for the mechanical rules (ref 0e04ca0d70e3). Night shift recorded 6 reinjection drills against data/m9 and data/j4 for CR-9209. Audit token 7975e54f5f24.

## Digest laboratory case 11

Mensah convened after fingerprint mismatch on charlie-stream (eu-central-seal); ticket S8R-13210. Measured tombstone_purge_depth=800, divergence=34%, reach_extra=3, members=4. Preset focus: stream row ordering under partial flush. Responders checked stamp-versus-head era and archived state_fingerprint.txt lines beside matrix lane tables. Ticket S8R-14210 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: epoching, lineage. Lab case 210 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash e93cc5662f58 attached for audit cross-reference only.
Case 210 shuffled entry emission order with seed 3570 while keeping canonical sort stable. Fingerprint equality for case 210 across shuffles confirms sorting is part of the contract. Case token cc42485d2d5e.
Legacy notes that recommended keeping data/j4 tails across recover-all for fast reopen are superseded; tails must collapse after a successful fleet pass.

## Digest laboratory case 12

War-room for fingerprint mismatch opened by Patel at echo-stamp/eu-west-replay under S8R-13211. Measured recover_one_bleed=841, divergence=47%, reach_extra=4, members=5. Preset focus: matrix lane authority versus embedded attach strings. Evidence pack for this ticket kept matrix lane tables and build_all.sh logs under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #211. Lexicon markers for this write-up: attachability, tombstoning. Lab case 211 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash c17054a6012a attached for audit cross-reference only.
Case 211 shuffled entry emission order with seed 3587 while keeping canonical sort stable. Fingerprint equality for case 211 across shuffles confirms sorting is part of the contract. Case token 2674e95e5c57.

## Digest laboratory case 13

Escalation S8R-13212: Chen tracked fingerprint mismatch across lima-journal in ap-south-fold. Measured head_era_delta=882, divergence=60%, reach_extra=5, members=6. Preset focus: sidecar stamp lag after sealed generation advance. On-call isolated recover-one; supporting artifacts included k7 stream tails. Gatekeeper reminder 212: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: foldback, resilver. Lab case 212 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash aa28cc3518bb attached for audit cross-reference only.
Case 212 shuffled entry emission order with seed 3604 while keeping canonical sort stable. Fingerprint equality for case 212 across shuffles confirms sorting is part of the contract. Case token 426e05ce6ed7.
Capacity review CR-9212 (af-south-tail) led by Nguyen examined sidecar stamp lag after sealed generation advance. Canary panel C-212 hid the fault until a delayed list probe. Operators postponed catalog writes until peer review completed for batch 212. Follow-up packet cites journal_format.md and recovery_semantics.md for the mechanical rules (ref be67f25a8c04). Night shift recorded 4 reinjection drills against data/m9 and data/j4 for CR-9212. Audit token e214cee3d6b3.
Design memo DM-8312 covers journal tail survival across recover-all. Authors noted instruction-facing failures map to environment packages (note 212). Writeup 212 stresses graded files come from ctl_s8 recover-all, not hand edits. Follow-up packet cites run_form.md and architecture.md for the mechanical rules (ref 076653607638). Reviewers Chen and Dubois signed DM-8312. Memo fingerprint 28406f72428a.

## Digest laboratory case 14

Rahman filed S8R-13213 when fingerprint mismatch recurred at oscar-matrix (ap-northeast-stamp). Measured sealed_retention=923, divergence=13%, reach_extra=6, members=7. Preset focus: journal tail survival across recover-all. Forensics retained bindings.toml probe_fixtures while cross-checking j4 directory listings. CI comment tw-213 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: resilver, hysteresis. Lab case 213 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 934c4ac6f4fe attached for audit cross-reference only.
Case 213 shuffled entry emission order with seed 3621 while keeping canonical sort stable. Fingerprint equality for case 213 across shuffles confirms sorting is part of the contract. Case token f2772abcc458.

## Digest laboratory case 15

Bridge call on fingerprint mismatch (uniform-boot, sa-east-ledger) owned by Almeida; id S8R-13214. Measured commit_max_era=964, divergence=26%, reach_extra=7, members=8. Preset focus: orphan staging files left by interrupted fold. Shift notes say operators confirmed sealed retention using build_all.sh logs. Lab policy note LP-214: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: backpressure, replication. Lab case 214 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 9b3137b521be attached for audit cross-reference only.
Case 214 shuffled entry emission order with seed 3638 while keeping canonical sort stable. Fingerprint equality for case 214 across shuffles confirms sorting is part of the contract. Case token 3a38add47767.

## Digest laboratory case 16

Dubois convened after fingerprint mismatch on tango-fold (af-south-tail); ticket S8R-13215. Measured staging_fold_ms=125, divergence=39%, reach_extra=8, members=9. Preset focus: boot-epoch list probes for retired catalog rows. Responders verified retired hard_limit stayed zero and archived supervisord stdout beside build_all.sh logs. Ticket S8R-14215 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: watchdog, lineage. Lab case 215 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 089995356a01 attached for audit cross-reference only.
Case 215 shuffled entry emission order with seed 3655 while keeping canonical sort stable. Fingerprint equality for case 215 across shuffles confirms sorting is part of the contract. Case token 295b38c10338.
Ops folklore that retired labels may keep positive hard_limit on epoch-2 probes is incorrect; retirement semantics forbid that.
Capacity review CR-9215 (eu-north-probe) led by Santos examined boot-epoch list probes for retired catalog rows. Dashboards stayed green on pass one while epoch probes later showed drift (series 215). Change window CW-215 required dual control before matrix or q9 edits. Follow-up packet cites architecture.md and journal_format.md for the mechanical rules (ref b8c29dd1c7bc). Night shift recorded 2 reinjection drills against data/m9 and data/j4 for CR-9215. Audit token ca73f6581d63.

## Digest laboratory case 17

War-room for fingerprint mismatch opened by Garcia at northwind-quota/ca-central-matrix under S8R-13216. Measured stamp_lag_ms=166, divergence=52%, reach_extra=0, members=10. Preset focus: fingerprint stability when t_ms jitters. Evidence pack for this ticket kept ctl_s8 recover-all transcripts and client_t4 list probes under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #216. Lexicon markers for this write-up: canarying, tombstoning. Lab case 216 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 2cd22b45130c attached for audit cross-reference only.
Case 216 shuffled entry emission order with seed 3672 while keeping canonical sort stable. Fingerprint equality for case 216 across shuffles confirms sorting is part of the contract. Case token 331372ae535a.
Design memo DM-8316 covers recover-one isolation against probe_fixtures staleness. Symptom closure for case 216 requires package-level repair, not output stubs. Reviewer Garcia rejected static stubs for recovery_run.v1 in case 216. Follow-up packet cites journal_format.md and recovery_semantics.md for the mechanical rules (ref 6e44353cbbe1). Reviewers Garcia and Nguyen signed DM-8316. Memo fingerprint d768b53fc42b.

## Digest laboratory case 18

Escalation S8R-13217: Jensen tracked fingerprint mismatch across foxtrot-capacity in me-central-boot. Measured tail_residue_count=207, divergence=5%, reach_extra=1, members=11. Preset focus: recover-one isolation against probe_fixtures staleness. On-call filed a readiness packet; supporting artifacts included client_t4 list probes. Gatekeeper reminder 217: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: saturation, resilver. Lab case 217 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash b88a5dcba050 attached for audit cross-reference only.
Case 217 shuffled entry emission order with seed 3689 while keeping canonical sort stable. Fingerprint equality for case 217 across shuffles confirms sorting is part of the contract. Case token a63dfb95a526.

## Digest laboratory case 19

Okoro filed S8R-13218 when fingerprint mismatch recurred at kilo-recovery (eu-north-probe). Measured attach_mismatch_pct=248, divergence=18%, reach_extra=2, members=12. Preset focus: tombstone era cutoffs interacting with sealed baselines. Forensics retained m9 stamp dumps while cross-checking matrix lane tables. CI comment tw-218 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: hysteresis, hysteresis. Lab case 218 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 5169e1162c2c attached for audit cross-reference only.
Case 218 shuffled entry emission order with seed 3706 while keeping canonical sort stable. Fingerprint equality for case 218 across shuffles confirms sorting is part of the contract. Case token 316cd218cfcc.
Capacity review CR-9218 (eu-south-epoch) led by Patel examined tombstone era cutoffs interacting with sealed baselines. Nightly green boards masked the issue until S8_BOOT_EPOCH simulation ran. Maintenance freeze MF-218 blocked solo edits to data/matrix and data/q9. Follow-up packet cites run_form.md and architecture.md for the mechanical rules (ref 406d048a1b19). Night shift recorded 5 reinjection drills against data/m9 and data/j4 for CR-9218. Audit token 575e74a73b48.

## Digest laboratory case 20

Bridge call on fingerprint mismatch (papa-sidecar, us-central-j4) owned by Nguyen; id S8R-13219. Measured era_skew=289, divergence=31%, reach_extra=3, members=13. Preset focus: corrupt JSONL tails preceding valid commit rows. Shift notes say operators reinjected staging residue using q9 ledger snapshots. Lab policy note LP-219: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: serialization, replication. Lab case 219 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 4aa155017e8f attached for audit cross-reference only.
Case 219 shuffled entry emission order with seed 3723 while keeping canonical sort stable. Fingerprint equality for case 219 across shuffles confirms sorting is part of the contract. Case token 0213f9be21e6.

## Digest laboratory case 21

Kowalski convened after fingerprint mismatch on delta-lane (ap-southeast-lane); ticket S8R-13220. Measured orphan_tmp_count=330, divergence=44%, reach_extra=4, members=3. Preset focus: q9 ledger eras lagging commit maxima. Responders collapsed deferred tails and archived j4 directory listings beside client_t4 list probes. Ticket S8R-14220 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: durability, lineage. Lab case 220 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 91cca5a6c659 attached for audit cross-reference only.
Case 220 shuffled entry emission order with seed 3740 while keeping canonical sort stable. Fingerprint equality for case 220 across shuffles confirms sorting is part of the contract. Case token fd024db7b8c6.
Pre-1.1 recovery halted the whole label on the first malformed JSONL line; resilience notes now require skip-and-continue.
Design memo DM-8320 covers cross-label apply transcript contamination. Repair guidance RG-220: fix sources under /app/environment, then rebuild. Memo DM-8420 repeats that /app/output artifacts must be driver-generated. Follow-up packet cites operator_runbook.md and run_form.md for the mechanical rules (ref b29773148aaa). Reviewers Kowalski and Berg signed DM-8320. Memo fingerprint f931f5842d26.

## Digest laboratory case 22

War-room for fingerprint mismatch opened by Ibrahim at bravo-catalog/eu-south-epoch under S8R-13221. Measured j4_file_count=371, divergence=57%, reach_extra=5, members=4. Preset focus: cross-label apply transcript contamination. Evidence pack for this ticket kept recovery_run.json excerpts and j4 directory listings under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #221. Lexicon markers for this write-up: monotonicity, tombstoning. Lab case 221 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 3b845b1e1930 attached for audit cross-reference only.
Case 221 shuffled entry emission order with seed 3757 while keeping canonical sort stable. Fingerprint equality for case 221 across shuffles confirms sorting is part of the contract. Case token 8d2415c8463d.
Capacity review CR-9221 (us-east-builder) led by Almeida examined cross-label apply transcript contamination. First recover-all looked healthy; boot-epoch 3 exposed residual disagreement. Two-person rule applied to lane table updates during incident 221. Follow-up packet cites operator_runbook.md and run_form.md for the mechanical rules (ref ce70a267a388). Night shift recorded 3 reinjection drills against data/m9 and data/j4 for CR-9221. Audit token d0447acabf67.

## Digest laboratory case 23

Escalation S8R-13222: Santos tracked fingerprint mismatch across charlie-stream in us-south-sidecar. Measured ledger_stale_era=412, divergence=10%, reach_extra=6, members=5. Preset focus: head-phase attach_id after matrix override. On-call checked stamp-versus-head era; supporting artifacts included state_fingerprint.txt lines. Gatekeeper reminder 222: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: partitioning, resilver. Lab case 222 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 9552bfade039 attached for audit cross-reference only.
Case 222 shuffled entry emission order with seed 3774 while keeping canonical sort stable. Fingerprint equality for case 222 across shuffles confirms sorting is part of the contract. Case token 361cdd8d6895.

## Digest laboratory case 24

Berg filed S8R-13223 when fingerprint mismatch recurred at echo-stamp (af-north-catalog). Measured fingerprint_drift=453, divergence=23%, reach_extra=7, members=6. Preset focus: double recover-all byte identity under residue reinjection. Forensics retained matrix lane tables while cross-checking build_all.sh logs. CI comment tw-223 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: replication, hysteresis. Lab case 223 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 670ac3a2bbf9 attached for audit cross-reference only.
Case 223 shuffled entry emission order with seed 3791 while keeping canonical sort stable. Fingerprint equality for case 223 across shuffles confirms sorting is part of the contract. Case token aebe6debf232.

## Digest laboratory case 25

Bridge call on fingerprint mismatch (lima-journal, us-east-builder) owned by Mensah; id S8R-13224. Measured apply_row_delta=494, divergence=36%, reach_extra=8, members=7. Preset focus: client_t4 list tuple agreement with recovery_run head rows. Shift notes say operators isolated recover-one using k7 stream tails. Lab policy note LP-224: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: checkpointing, replication. Lab case 224 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash bc76dc71e49c attached for audit cross-reference only.
Case 224 shuffled entry emission order with seed 3808 while keeping canonical sort stable. Fingerprint equality for case 224 across shuffles confirms sorting is part of the contract. Case token 038a5c63dcd8.
Capacity review CR-9224 (eu-west-replay) led by Jensen examined client_t4 list tuple agreement with recovery_run head rows. Early metrics for run 224 under-reported attach and era skew. Peer sign-off from Patel was mandatory before lane changes. Follow-up packet cites recovery_semantics.md and operator_runbook.md for the mechanical rules (ref cdeba55dc4e0). Night shift recorded 6 reinjection drills against data/m9 and data/j4 for CR-9224. Audit token a0846b35b045.
Design memo DM-8324 covers stream row ordering under partial flush. Postmortem action item 224: keep fixes in supervisor code paths, not tests/. Emitter owners confirmed driver regeneration for series 224. Follow-up packet cites architecture.md and journal_format.md for the mechanical rules (ref e1b711723443). Reviewers Mensah and Rahman signed DM-8324. Memo fingerprint 80b4dfd822e5.

## Digest laboratory case 26

Patel convened after fingerprint mismatch on oscar-matrix (us-west-quota); ticket S8R-13225. Measured boot_epoch_ghost_hits=535, divergence=49%, reach_extra=0, members=8. Preset focus: stream row ordering under partial flush. Responders skipped a corrupt JSONL line in a dry run and archived bindings.toml probe_fixtures beside j4 directory listings. Ticket S8R-14225 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: idempotence, lineage. Lab case 225 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 6f4ba586ebca attached for audit cross-reference only.
Case 225 shuffled entry emission order with seed 3825 while keeping canonical sort stable. Fingerprint equality for case 225 across shuffles confirms sorting is part of the contract. Case token 555d7d6379bc.
An early capacity memo claimed stream attach_id strings always win over matrix lanes; that guidance was withdrawn after the builder-farm attach audit.

## Digest laboratory case 27

War-room for fingerprint mismatch opened by Chen at uniform-boot/eu-central-seal under S8R-13226. Measured matrix_override_hits=576, divergence=62%, reach_extra=1, members=9. Preset focus: matrix lane authority versus embedded attach strings. Evidence pack for this ticket kept build_all.sh logs and matrix lane tables under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #226. Lexicon markers for this write-up: quiescence, tombstoning. Lab case 226 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 8ec938830745 attached for audit cross-reference only.
Case 226 shuffled entry emission order with seed 3842 while keeping canonical sort stable. Fingerprint equality for case 226 across shuffles confirms sorting is part of the contract. Case token e33ee0bdb3f3.

## Digest laboratory case 28

Escalation S8R-13227: Rahman tracked fingerprint mismatch across tango-fold in eu-west-replay. Measured corrupt_line_skips=617, divergence=15%, reach_extra=2, members=10. Preset focus: sidecar stamp lag after sealed generation advance. On-call verified retired hard_limit stayed zero; supporting artifacts included supervisord stdout. Gatekeeper reminder 227: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: reentrancy, resilver. Lab case 227 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash a5b2c0fcc12e attached for audit cross-reference only.
Case 227 shuffled entry emission order with seed 3859 while keeping canonical sort stable. Fingerprint equality for case 227 across shuffles confirms sorting is part of the contract. Case token 3e133cd1db7e.
Capacity review CR-9227 (sa-east-ledger) led by Kowalski examined sidecar stamp lag after sealed generation advance. Canary panel C-227 hid the fault until a delayed list probe. Operators postponed catalog writes until peer review completed for batch 227. Follow-up packet cites journal_format.md and recovery_semantics.md for the mechanical rules (ref 6e44353cbbe1). Night shift recorded 4 reinjection drills against data/m9 and data/j4 for CR-9227. Audit token c8ef5273136b.

## Digest laboratory case 29

Almeida filed S8R-13228 when fingerprint mismatch recurred at northwind-quota (ap-south-fold). Measured tombstone_purge_depth=658, divergence=28%, reach_extra=3, members=11. Preset focus: journal tail survival across recover-all. Forensics retained ctl_s8 recover-all transcripts while cross-checking client_t4 list probes. CI comment tw-228 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: lineage, hysteresis. Lab case 228 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 1a0ac2d7e8de attached for audit cross-reference only.
Case 228 shuffled entry emission order with seed 3876 while keeping canonical sort stable. Fingerprint equality for case 228 across shuffles confirms sorting is part of the contract. Case token d4e537f3084f.
Design memo DM-8328 covers orphan staging files left by interrupted fold. Debug path 228 stays inside /app/environment until list and ledger agree. Acceptance packet AP-228 marks hand-written /app/output as insufficient. Follow-up packet cites recovery_semantics.md and operator_runbook.md for the mechanical rules (ref 2796a23c524c). Reviewers Almeida and Jensen signed DM-8328. Memo fingerprint 084ae2f3c4e5.

## Digest laboratory case 30

Bridge call on fingerprint mismatch (foxtrot-capacity, ap-northeast-stamp) owned by Dubois; id S8R-13229. Measured recover_one_bleed=699, divergence=41%, reach_extra=4, members=12. Preset focus: orphan staging files left by interrupted fold. Shift notes say operators filed a readiness packet using client_t4 list probes. Lab policy note LP-229: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: provenance, replication. Lab case 229 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 817e0e54671d attached for audit cross-reference only.
Case 229 shuffled entry emission order with seed 3893 while keeping canonical sort stable. Fingerprint equality for case 229 across shuffles confirms sorting is part of the contract. Case token b417b2d59dcd.

## Digest laboratory case 31

Garcia convened after fingerprint mismatch on kilo-recovery (sa-east-ledger); ticket S8R-13230. Measured head_era_delta=740, divergence=54%, reach_extra=5, members=13. Preset focus: boot-epoch list probes for retired catalog rows. Responders ran a cold-boot simulation and archived m9 stamp dumps beside matrix lane tables. Ticket S8R-14230 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: coalescing, lineage. Lab case 230 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 1420e2816b70 attached for audit cross-reference only.
Case 230 shuffled entry emission order with seed 3910 while keeping canonical sort stable. Fingerprint equality for case 230 across shuffles confirms sorting is part of the contract. Case token f6c9ac26b5b7.
A short-lived runbook allowed recover-one to refresh all sidecar stamps; that behavior was revoked because isolation probes became flaky.
Capacity review CR-9230 (me-central-boot) led by Berg examined boot-epoch list probes for retired catalog rows. Dashboards stayed green on pass one while epoch probes later showed drift (series 230). Change window CW-230 required dual control before matrix or q9 edits. Follow-up packet cites architecture.md and journal_format.md for the mechanical rules (ref e178da0a2305). Night shift recorded 2 reinjection drills against data/m9 and data/j4 for CR-9230. Audit token 4f86999a43d2.

## Digest laboratory case 32

War-room for fingerprint mismatch opened by Jensen at papa-sidecar/af-south-tail under S8R-13231. Measured sealed_retention=781, divergence=7%, reach_extra=6, members=3. Preset focus: fingerprint stability when t_ms jitters. Evidence pack for this ticket kept q9 ledger snapshots and build_all.sh logs under the same incident folder. Package edits without /app/environment/scripts/build_all.sh were rejected in review #231. Lexicon markers for this write-up: fencing, tombstoning. Lab case 231 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 98a30238a831 attached for audit cross-reference only.
Case 231 shuffled entry emission order with seed 3927 while keeping canonical sort stable. Fingerprint equality for case 231 across shuffles confirms sorting is part of the contract. Case token a0c8c8072684.

## Digest laboratory case 33

Escalation S8R-13232: Okoro tracked fingerprint mismatch across delta-lane in ca-central-matrix. Measured commit_max_era=822, divergence=20%, reach_extra=7, members=4. Preset focus: recover-one isolation against probe_fixtures staleness. On-call collapsed deferred tails; supporting artifacts included j4 directory listings. Gatekeeper reminder 232: rebuild via build_all.sh before ctl_s8 recover-all. Lexicon markers for this write-up: compaction, resilver. Lab case 232 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash a7294cdb0488 attached for audit cross-reference only.
Case 232 shuffled entry emission order with seed 3944 while keeping canonical sort stable. Fingerprint equality for case 232 across shuffles confirms sorting is part of the contract. Case token 0f6e86f365ba.
Design memo DM-8332 covers tombstone era cutoffs interacting with sealed baselines. Authors noted instruction-facing failures map to environment packages (note 232). Writeup 232 stresses graded files come from ctl_s8 recover-all, not hand edits. Follow-up packet cites run_form.md and architecture.md for the mechanical rules (ref 64888342a6b8). Reviewers Okoro and Ibrahim signed DM-8332. Memo fingerprint 273ebe2c00b9.

## Digest laboratory case 34

Nguyen filed S8R-13233 when fingerprint mismatch recurred at bravo-catalog (me-central-boot). Measured staging_fold_ms=863, divergence=33%, reach_extra=8, members=5. Preset focus: tombstone era cutoffs interacting with sealed baselines. Forensics retained recovery_run.json excerpts while cross-checking j4 directory listings. CI comment tw-233 refused wrapper-only changes that skipped the rebuild path. Lexicon markers for this write-up: tombstoning, hysteresis. Lab case 233 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 4426d0de5681 attached for audit cross-reference only.
Case 233 shuffled entry emission order with seed 3961 while keeping canonical sort stable. Fingerprint equality for case 233 across shuffles confirms sorting is part of the contract. Case token 8d77ab4321c0.
Capacity review CR-9233 (ap-southeast-lane) led by Chen examined tombstone era cutoffs interacting with sealed baselines. Nightly green boards masked the issue until S8_BOOT_EPOCH simulation ran. Maintenance freeze MF-233 blocked solo edits to data/matrix and data/q9. Follow-up packet cites run_form.md and architecture.md for the mechanical rules (ref cfb7c1737850). Night shift recorded 5 reinjection drills against data/m9 and data/j4 for CR-9233. Audit token 7454a8fc0df9.

## Digest laboratory case 35

Bridge call on fingerprint mismatch (charlie-stream, eu-north-probe) owned by Kowalski; id S8R-13234. Measured stamp_lag_ms=904, divergence=46%, reach_extra=0, members=6. Preset focus: corrupt JSONL tails preceding valid commit rows. Shift notes say operators checked stamp-versus-head era using state_fingerprint.txt lines. Lab policy note LP-234: source fixes under /app/environment require build_all.sh. Lexicon markers for this write-up: sidecaring, replication. Lab case 234 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 194b2a911da6 attached for audit cross-reference only.
Case 234 shuffled entry emission order with seed 3978 while keeping canonical sort stable. Fingerprint equality for case 234 across shuffles confirms sorting is part of the contract. Case token b24f2106b067.

## Digest laboratory case 36

Ibrahim convened after fingerprint mismatch on echo-stamp (us-central-j4); ticket S8R-13235. Measured tail_residue_count=945, divergence=59%, reach_extra=1, members=7. Preset focus: q9 ledger eras lagging commit maxima. Responders validated matrix override and archived matrix lane tables beside build_all.sh logs. Ticket S8R-14235 blocked promotion until scripts/build_all.sh rebuilt binaries. Lexicon markers for this write-up: epoching, lineage. Lab case 235 recomputed slim-object hashes offline and compared to state_fingerprint.txt. Reference hash 199bd3a0d4cd attached for audit cross-reference only.
Case 235 shuffled entry emission order with seed 3995 while keeping canonical sort stable. Fingerprint equality for case 235 across shuffles confirms sorting is part of the contract. Case token d20a256ddbae.
A 2023 fingerprint sketch hashed t_ms into the digest; driver 2.4 removed timing from the canonical hash entirely.

## Negative examples (obsolete)

- Hashing full entries including `t_ms` produced unstable digests under load.
- Sorting only by `run_label` without `segment_id` and `phase` collided distinct apply/head pairs.
- Uppercase hex output failed verifier comparisons that expect lowercase.

Follow Digest construction above.


## Cross-document dependencies

- Digest construction and t_ms zeroing: this document.
- Which segment_ids appear as apply rows: journal_format.md.
- Head attach_id after matrix override: architecture.md + operator_runbook.md lane binding.
- When graded files must exist: this document + operator_runbook.md recover-one rules.
