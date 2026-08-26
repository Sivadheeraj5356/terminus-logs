package main

// paginate returns a slice of items starting at offset with length limit.
// If limit <= 0, all items from offset are returned.
func paginate[T any](items []T, offset, limit int) []T {
	if offset >= len(items) {
		return nil
	}
	items = items[offset:]
	if limit > 0 && limit < len(items) {
		items = items[:limit]
	}
	return items
}
