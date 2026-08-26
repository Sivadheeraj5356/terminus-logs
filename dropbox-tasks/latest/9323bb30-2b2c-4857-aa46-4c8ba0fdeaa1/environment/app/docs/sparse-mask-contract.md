# Sparse mask + quantized tile contract

Sparse attention mask uses BSR-style metadata:

- `indptr`: length `n_q + 1`, nondecreasing, `indptr[0] = 0`
- `indices`: length `nnz`, each entry a K-tile index in `0..n_k`
- `packed_mask`: bit-packed little-endian bytes; bit `b` of the stream corresponds to the `b`-th entry of `indices` (1 = keep)

**Shape rehydration order:** expand kept `(qi, kj)` pairs by walking `qi` ascending, and within each `qi` walking the `indices[indptr[qi]:indptr[qi+1]]` slice **as stored**. Do **not** sort `indices` globally by `kj` before expansion.

**Mask vs residency (axiom):** kept pairs govern **softmax visitation and `visit_checksum` only**. They do not shrink the block-table page set. Planning still allocates every `(h, kj)` slot.

Int8 K-tile payloads in the pack: for each head, `scale` (f32) and `zero_point` (i8). Dequantized sample `x = (q - zero_point) * scale`. Tile local max `m_tile` is the max dequantized value over the tile window; `ell_tile = sum(exp(x - m_tile))` over the window.
