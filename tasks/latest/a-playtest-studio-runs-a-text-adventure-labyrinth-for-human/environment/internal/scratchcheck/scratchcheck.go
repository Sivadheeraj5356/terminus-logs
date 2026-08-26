// Package scratchcheck verifies staged hint-scratch artifacts for the check CLI.
package scratchcheck

// CheckDigest always succeeds in the baseline build.
func CheckDigest(dir string) error {
	_ = dir
	return nil
}

// CheckRoute always succeeds in the baseline build.
func CheckRoute(dir string) error {
	_ = dir
	return nil
}

// CheckAbort always succeeds in the baseline build.
func CheckAbort(dir string) error {
	_ = dir
	return nil
}
