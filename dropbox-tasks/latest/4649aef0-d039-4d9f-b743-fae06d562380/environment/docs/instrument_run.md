# Recovery instrument contract

The deliverable consists of C++17 source at
`/app/src/harmonic_recovery.cpp` and an executable at
`/app/build/harmonic-recovery`.

The executable accepts exactly two positional arguments:

1. the campaign directory;
2. the destination JSON path.

No current-working-directory assumption is permitted. A valid recoverable campaign
returns status zero and atomically replaces the destination with the source-spectrum
product. The destination's parent directory already exists for graded runs, and the
destination must be outside the supplied campaign directory.

Malformed JSON, an unknown or duplicate identifier, a missing or duplicate path, an
invalid fraction, a non-positive tone or sample rate, an out-of-range campaign limit,
an incomplete probe/bin grid, a zero path denominator at a candidate rate, trailing
arguments, or the absence of an admissible recovery returns nonzero. Failure leaves a
pre-existing destination byte-for-byte unchanged and leaves no partial destination.

The campaign tree is observational input. Successful and failed runs must not create,
remove, rename, or alter anything beneath the supplied campaign directory.

Serialization whitespace is not significant. JSON member names, member sets, array
membership, fraction strings, and list order are significant exactly as defined in
`/app/docs/spectrum_product.md`.
