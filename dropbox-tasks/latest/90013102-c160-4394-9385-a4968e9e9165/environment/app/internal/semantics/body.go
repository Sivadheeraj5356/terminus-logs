package semantics

import (
	"fmt"
	"sigproxy/internal/digest"
)

const DefaultBodyLimit = 1048576

func ValidateBody(body []byte, limit int) error {
	if limit <= 0 {
		limit = DefaultBodyLimit
	}
	if len(body) > limit {
		return fmt.Errorf("entity body exceeds limit of %d bytes", limit)
	}
	return nil
}

func BodyDigest(body []byte) string {
	return digest.SHA256(body)
}

func BodyLength(body []byte) int {
	return len(body)
}
