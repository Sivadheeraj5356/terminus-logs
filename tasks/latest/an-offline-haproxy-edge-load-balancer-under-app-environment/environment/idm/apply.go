package idm

// Mark is the public wrapper around dur_mark.
func Mark(tx string) error {
	return dur_mark(tx)
}

// Seen is the public wrapper around dur_seen.
func Seen(tx string) (bool, error) {
	return dur_seen(tx)
}
