# Changelog

## Unreleased
- Checkpoint/rematerialization mode is being brought up to parity with the
  non-checkpointed path. Until it lands, checkpointed runs may diverge from the
  baseline a few steps in — see spec section 10 and the failure catalogue.

## rev 6
- Pinned the Adam epsilon placement and the layer-3 gradient-clip threshold in
  the design note after two regressions traced back to "equivalent" rewrites.

## rev 5
- Documented the ragged-last-batch rule and its interaction with the PRNG stream
  across epoch boundaries.
