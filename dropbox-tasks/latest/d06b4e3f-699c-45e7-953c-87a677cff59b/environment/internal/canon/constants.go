// Package canon implements the canonical byte encoding of events and
// checkpoint signing material described in CHAINAUDIT-SPEC.md. Every hash or
// signature in this system is computed over these exact byte layouts; changing
// a single field order or width here invalidates every checkpoint ever
// written.
package canon

import "crypto/sha256"

const (
	PayloadNormal    byte = 0x00
	PayloadTombstone byte = 0x01
)

// TombstoneSentinel is substituted for the payload field of any event with
// tombstone=1. Erased events must not be canonicalized with their (now empty)
// raw payload column: two independently-erased events would otherwise
// canonicalize to indistinguishable byte strings, and an event that
// legitimately always had an empty payload would hash identically to one that
// was erased after the fact. See the spec's tombstone changelog entry for the
// incident that prompted this.
var TombstoneSentinel = sha256.Sum256([]byte("CHAINAUDIT-TOMBSTONE-SENTINEL-v1"))
