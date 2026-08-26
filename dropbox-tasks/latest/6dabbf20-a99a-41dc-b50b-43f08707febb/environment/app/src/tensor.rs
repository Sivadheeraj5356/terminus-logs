// Dense row-major f64 matrix with sequential (order-pinned) reductions.
// See engine_design.md sec. 8.1 and 14.
//
// Reductions (matmul inner products, column sums, sums of squares) must
// accumulate left-to-right in index order. No parallel/hashmap reductions.
//
// TODO: implement the Mat type and its ops.
