// Package version decides which canonical encoding a given event uses.
package version

const (
	V1 byte = 0x01
	V2 byte = 0x02
)

// Encoding returns the canonical encoding version for an event timestamped
// eventTs in a stream whose migrated_at is migratedAt. A stream that has
// never been migrated (migratedAt == nil) encodes every event as V1. Once a
// stream has a migration point, events at or after it encode as V2; events
// from before it stay V1 even though they now live in the same stream, the
// same checkpoint batch, and possibly the same page of query results as V2
// events. The decision is made per event, never once per stream.
func Encoding(migratedAt *int64, eventTs int64) byte {
	if migratedAt == nil {
		return V1
	}
	if eventTs >= *migratedAt {
		return V2
	}
	return V1
}
