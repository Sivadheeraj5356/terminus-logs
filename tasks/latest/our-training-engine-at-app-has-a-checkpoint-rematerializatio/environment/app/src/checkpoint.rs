// Resumable snapshots (weights + optimizer moments + step + PRNG state) and the
// state-fingerprint hashes recorded in the database. Binary layout, checksum,
// and load-time validation are in engine_design.md sec. 15. A truncated or
// corrupt snapshot must be rejected before any training happens.
//
// TODO: implement save/load and the FNV-1a fingerprints.
