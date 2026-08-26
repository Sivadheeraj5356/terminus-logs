# Acquisition export notes

CELL/3 shards are transport units, not statistical batches. Instruments may
rename files during transfer or split one run across several files. An
observation identifier remains stable across those operations and is the
identity used when exports overlap.

Retention time units may differ after instrument calibration. A run-level
positive scale and offset preserves order and therefore preserves normalized
coordinates. Confidence is carried into the attestation as provenance but does
not change ordering.
