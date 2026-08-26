package hash

import (
	"crypto/sha256"
	"encoding/hex"
)

// DomainHash binds a domain separator to a payload.
// Contract (docs/pipeline.md): SHA256(domain + "\n" + payload) hex-encoded.
func DomainHash(domain string, payload []byte) string {
	buf := make([]byte, 0, len(domain)+1+len(payload))
	buf = append(buf, domain...)
	buf = append(buf, '\n')
	buf = append(buf, payload...)
	sum := sha256.Sum256(buf)
	return hex.EncodeToString(sum[:])
}

// HexSHA256 is a plain SHA-256 of payload without a domain separator.
func HexSHA256(payload []byte) string {
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

// Truncate returns the first n hex characters of a digest (n<=len).
func Truncate(digest string, n int) string {
	if n <= 0 || n > len(digest) {
		return digest
	}
	return digest[:n]
}
