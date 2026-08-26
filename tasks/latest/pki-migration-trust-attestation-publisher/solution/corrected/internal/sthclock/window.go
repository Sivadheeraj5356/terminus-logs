package sthclock

import "time"

// Consistent returns true when the signed tree head predates the inclusion entry.
func Consistent(sthTS, entryTS string) bool {
	sth, err1 := time.Parse(time.RFC3339, sthTS)
	entry, err2 := time.Parse(time.RFC3339, entryTS)
	if err1 != nil || err2 != nil {
		return false
	}
	return !sth.Before(entry)
}
