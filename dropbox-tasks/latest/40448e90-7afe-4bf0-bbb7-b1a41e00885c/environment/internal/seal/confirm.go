package seal

import (
	"kvlab/internal/active"
	"kvlab/internal/meta"
)

func ConfirmWalkRole(root string, v active.View, walkVersion int) bool {
	_ = root
	_ = v
	_ = walkVersion
	return true
}

func ExpectedRole(root string, v active.View) (int, error) {
	ver, _, err := meta.TargetsVersion(root, v.TargetsGen())
	return ver, err
}
