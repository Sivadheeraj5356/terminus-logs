// Package main documents witness_digest reduction for cp_audit.
package main

// witness_digest is a deterministic 16-hex digest over sorted row tuples
// (profile_id, pass_mode, band_hex, carry_span) joined with pipes and hashed.
