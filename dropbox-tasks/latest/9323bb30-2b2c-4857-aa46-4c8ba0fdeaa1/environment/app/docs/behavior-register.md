# Behavior register

Offline machine-learning contracts for FlashAttention KV-cache residency evaluation (transformer inference features).

| ID | Behavior | Spec |
|----|----------|------|
| BR-001 | Tile Br/Bc sizing from profile caps and head_dim | tile-schedule-contract.md |
| BR-002 | Tile visitation order is row-major over Q-tiles then K-tiles | tile-schedule-contract.md |
| BR-003 | Online softmax m/ℓ rescale uses α = exp(m_old − m_new) on both ℓ and O_acc | online-softmax-contract.md |
| BR-004 | Logical→physical block table pages are block_tokens wide | block-table-contract.md |
| BR-005 | Free-list reclaim is LIFO; advance compact only when free_ratio > threshold | block-table-contract.md |
| BR-006 | Sparse mask packed bits are little-endian; rehydrate in ascending logical block order | sparse-mask-contract.md |
| BR-007 | Int8 tile dequant uses per-head scale and zero_point | sparse-mask-contract.md |
| BR-008 | Residency.bin magic KVT1; multi-run run_epoch increments on advance; plan resets epoch to 0; compact_gen persists | residency-seal-schema.md / cli-reference.md |
| BR-009 | seal_digest = SHA-256 hex of canonical seal payload including prior_fold, compact_gen, visit_checksum, merkle_tip, compiler_epoch, rebuild_nonce, schedule_crc, and residue_u64 (no trailing newline) | residency-seal-schema.md |
| BR-020 | build.sh writes epoch with rebuild_nonce 0; rebuild.sh writes non-zero rebuild_nonce; seal folds both into seal_digest | residency-seal-schema.md / cli-reference.md |

| BR-018 | merkle_tip SHA-256 fold on advance; plan resets tip to 0 after trailer check | residency-seal-schema.md |
| BR-019 | seal writes spine_trailer.hex = tip XOR spine_salt; plan rejects stale trailer | residency-seal-schema.md / cli-reference.md |
| BR-010 | kvtile-seal refuses when pages_resident == 0 (exit 2); missing residency.bin ≡ empty | cli-reference.md |
| BR-015 | kvtile-advance treats missing residency.bin as empty ledger and exits 0 after persist | cli-reference.md |
| BR-011 | kvtile-advance never allocates or pops the free stack; only plan reallocates freed pages (LIFO) | block-table-contract.md |
| BR-012 | Cascade hook: tile_scheduler residency mutation constrains seal page set | module-scope.md |
| BR-013 | prior_fold from `{KVTILE_APP_ROOT}/var/prior_seal.hex` (or 64 zeros); plan deletes prior file; seal persists new digest | residency-seal-schema.md / cli-reference.md / runtime-env.md |
| BR-014 | Successful densifying compact increments compact_gen; seal payload folds compact_gen | block-table-contract.md / residency-seal-schema.md |
| BR-016 | Plan allocates all n_heads×n_k pages; sparse mask gates softmax visits only | tile-schedule-contract.md / sparse-mask-contract.md |
| BR-017 | visit_checksum XOR fold over mask-kept (h,qi,kj) visits; persisted in ledger; folded into seal_digest | residency-seal-schema.md / online-softmax-contract.md |
| BR-021 | Plan writes /app/data/schedule.mir (SCH1 + visit triples); seal folds IEEE CRC32 of mir bytes as schedule_crc | residency-seal-schema.md |
| BR-022 | residue_u64 seeds at plan from visit_checksum||mask_bits; rotate_left(7) parent-chain after merkle_tip on advance; folded after schedule_crc | residency-seal-schema.md |
