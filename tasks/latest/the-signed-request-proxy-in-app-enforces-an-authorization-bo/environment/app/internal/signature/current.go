package signature

import (
	"sigproxy/internal/semantics"
)

// BuildCurrentV2 constructs the v2 canonical message from a semantic request.
func BuildCurrentV2(sem *semantics.Request) (string, error) {
	msg, err := BuildMessage(sem, 2)
	if err != nil {
		return "", err
	}
	return msg.Raw, nil
}
