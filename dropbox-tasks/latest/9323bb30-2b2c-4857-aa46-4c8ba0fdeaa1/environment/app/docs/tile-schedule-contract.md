# Tile schedule contract

Given profile fields `br_cap`, `bc_cap`, `head_dim`, sequence length `seq_len`, and number of heads `n_heads`:

- `Br = min(br_cap, head_dim)`
- `Bc = min(bc_cap, head_dim)`
- Number of Q-tiles along sequence: `n_q = ceil(seq_len / Br)`
- Number of K-tiles along sequence: `n_k = ceil(seq_len / Bc)`

Visitation order for planning: for each head `h` in `0..n_heads`, for each Q-tile `qi` in `0..n_q`, for each K-tile `kj` in `0..n_k`, emit tile key `(h, qi, kj)`.

A tile is **resident** only after its physical page has been allocated in the block table. Planning must allocate one physical page per unique `(h, kj)` K-tile (shared across Q-tiles for the same head/K-tile). Q-tile metadata is recorded but does not allocate a separate page.

**Page allocation scope (axiom):** allocation is **unconditional** over all `n_heads × n_k` logical K-tile slots. The sparse mask does **not** decide which pages become resident. After a successful plan, `pages_resident` equals `n_heads * n_k` (before any later advance release/compact). The mask only decides which `(qi, kj)` pairs contribute online-softmax updates during the visitation walk (see online-softmax-contract.md and sparse-mask-contract.md).
