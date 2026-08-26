package serial

import "fmt"

// Newer reports whether a is chronologically newer than b.
func Newer(a, b uint32) bool {
	return a > b
}

func Max(a, b uint32) uint32 {
	if a > b {
		return a
	}
	return b
}

func Allocate(candidate, previous uint32, changed bool) uint32 {
	if !changed {
		return previous
	}
	if Newer(candidate, previous) {
		return candidate
	}
	return previous + 1
}

func Format(u uint32) string {
	return fmt.Sprintf("%d", u)
}
