package signature

import (
	"sigproxy/internal/semantics"
)

// BuildLegacyV1 constructs the legacy v1 canonical message.
func BuildLegacyV1(sem *semantics.Request) (string, error) {
	msg, err := BuildMessage(sem, 1)
	if err != nil {
		return "", err
	}
	return msg.Raw, nil
}
