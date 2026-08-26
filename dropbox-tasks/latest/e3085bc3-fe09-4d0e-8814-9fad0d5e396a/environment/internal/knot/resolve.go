package knot

import (
	"fmt"
	"path/filepath"

	"imlab/internal/model"
)

// Covenant returns the stamp epoch for the authority pin.
func Covenant(s model.AuthorityStamp) int {
	return s.A*3 + s.B*2 + s.C
}

// ResolvePolicy picks a policy bundle path from the pin/index/stamp triple.
func ResolvePolicy(authDir string, pin model.AuthorityPin, idx model.AuthorityIndex, stamp model.AuthorityStamp) (string, error) {
	want := Covenant(stamp)
	key := pin.Key
	if pin.Ep != want {
		key = "live"
	}
	var rel string
	switch key {
	case "arm":
		rel = idx.Arm
	case "hold":
		rel = idx.Hold
	default:
		rel = idx.Live
	}
	if rel == "" {
		return "", fmt.Errorf("empty lane for key %q", key)
	}
	return filepath.Clean(filepath.Join(authDir, rel)), nil
}
