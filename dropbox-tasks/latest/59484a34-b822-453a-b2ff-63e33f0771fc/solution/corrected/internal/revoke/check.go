package revoke

import (
	"encoding/json"
	"os"
)

// Revoked reports whether a serial is listed in the revocation bundle.
func Revoked(path, serial string) bool {
	b, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	var f struct {
		Revocations []struct {
			Serial    string `json:"serial"`
			RevokedAt string `json:"revoked_at"`
		} `json:"revocations"`
	}
	if err := json.Unmarshal(b, &f); err != nil {
		return false
	}
	for _, r := range f.Revocations {
		if r.Serial == serial {
			return true
		}
	}
	return false
}
