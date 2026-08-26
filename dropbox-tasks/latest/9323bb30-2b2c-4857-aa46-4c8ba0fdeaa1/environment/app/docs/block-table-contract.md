# Block table / paged residency contract

Physical pages are fixed width `block_tokens` (from profile). Logical K-tile index `L = h * n_k + kj` maps to exactly one physical page id while resident. The block-table allocator owns physical page ids for KV tensor tiles.

- Allocation: if the free stack is non-empty, **pop LIFO** (reuse the most recently freed physical id); otherwise append a new page id = current `page_count` and increment `page_count`. On plan construction, allocate **every** logical `L = h * n_k + kj` for `h ∈ [0,n_heads)`, `kj ∈ [0,n_k)` — never skip a slot because the sparse mask dropped that K-tile from softmax visits.
- Free / release: remove the logical→physical map entry and **push** the physical id onto the free stack (LIFO top at the end of the stack vector).
- `free_ratio = free_stack_len / max(page_count, 1)`
- `kvtile-advance` never allocates and never pops the free stack. It may `--release-logical <L>` (push freed ids) and/or `--compact`. Compact applies only when `free_ratio > compact_threshold` (profile). Otherwise compact is a no-op on the free stack / map, but advance still increments `run_epoch`.
- After a **successful** compact, physical page ids of remaining map entries are renumbered densely from 0 in ascending prior logical order; the free stack is cleared; `page_count` becomes `map.len()`; **`compact_gen` increments by 1**.
- Replan (`kvtile-plan` when a valid ledger already exists): release every currently mapped page onto the free stack (preserving high-water `page_count`), clear the map, then allocate required logicals — **LIFO reuse** of freed pages before appending. Corrupt/missing ledgers start empty. Plan always sets `run_epoch = 0` and does **not** reset `compact_gen` (compact_gen persists across replan).
- Missing `/app/data/residency.bin` for `kvtile-advance` / `kvtile-seal`: treat as empty residency (same empty baseline as a fresh plan). Advance exits 0 after persist; seal exits 2 when `pages_resident == 0` (see cli-reference.md).

Ouroboros constraint: `seal_digest` must fold physical page ids in ascending logical map order for the current residency epoch (tile scheduler owns the map). Digests also fold `prior_fold` and `compact_gen` (see residency-seal-schema.md). A seal that sorts by physical id alone, ignores LIFO remapping after replan, or drops `compact_gen` after a successful densifying compact is invalid.

Densifying compact renumbers physical ids; the next advance fold must use post-compact logical-order phys ids so `merkle_tip` tracks the remapped map.
