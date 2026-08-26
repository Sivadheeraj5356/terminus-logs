package semver

import "strings"

// GTE returns whether version is greater than or equal to minimum.
// Baseline alphabetically/string compares; production gate expects numeric X.Y.Z.
func GTE(version, minimum string) bool {
	return strings.Compare(version, minimum) >= 0
}
