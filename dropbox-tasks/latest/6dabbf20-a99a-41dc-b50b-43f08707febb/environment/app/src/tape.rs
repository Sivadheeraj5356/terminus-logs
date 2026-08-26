// The autodiff tape: parameters, the forward pass that records activations,
// and the reverse pass. The layer-2 block is the rematerialized one; on the
// backward pass it is recomputed from the retained layer-1 output with the
// PRNG restored to its pre-dropout state. See engine_design.md sec. 10.
//
// Also: layer-3 gradient clipping (sec. 13) and the global gradient norm.
//
// TODO: implement.
