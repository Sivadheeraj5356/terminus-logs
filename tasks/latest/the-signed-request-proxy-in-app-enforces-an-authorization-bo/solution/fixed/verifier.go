package signature

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"fmt"
	"strings"

	"sigproxy/internal/keyring"
	"sigproxy/internal/semantics"
)

type VerifyResult struct {
	OK               bool
	Reason           string
	SignatureVersion int
	CacheHit         bool
	AuthorityDigest  string
	CanonicalDigest  string
}

func Verify(sem *semantics.Request, sigHeader string, kr *keyring.Keyring, cache *keyring.AuthorityCache, catalogDigest string) VerifyResult {
	if sigHeader == "" {
		return VerifyResult{OK: false, Reason: "missing_signature"}
	}

	parts := strings.SplitN(sigHeader, " ", 2)
	if len(parts) != 2 {
		return VerifyResult{OK: false, Reason: "malformed_signature_header"}
	}
	versionLabel := parts[0]
	sigHex := parts[1]

	var version int
	switch versionLabel {
	case "v1":
		version = 1
	case "v2":
		version = 2
	default:
		return VerifyResult{OK: false, Reason: "unsupported_signature_version"}
	}

	if version != sem.SignatureVersion {
		return VerifyResult{OK: false, Reason: "signature_version_mismatch"}
	}

	key, ok := kr.Lookup(sem.Tenant, sem.KeyID, sem.KeyEpoch)
	if !ok {
		return VerifyResult{OK: false, Reason: "unknown_key"}
	}
	if key.Revoked {
		return VerifyResult{OK: false, Reason: "key_revoked"}
	}

	allowed := false
	for _, p := range key.AllowedProfiles {
		if p == sem.ProfileID {
			allowed = true
			break
		}
	}
	if !allowed {
		return VerifyResult{OK: false, Reason: "profile_not_allowed"}
	}

	secret, cacheHit := cache.Get(key.Tenant, key.KeyID, key.KeyEpoch, sem.ProfileID, sem.ProfileEpoch, catalogDigest)
	if secret == nil {
		secret = key.Secret
		cache.Put(key.Tenant, key.KeyID, key.KeyEpoch, sem.ProfileID, sem.ProfileEpoch, secret, key.AllowedVersions, catalogDigest)
		cacheHit = false
	}

	msg, err := BuildMessage(sem, version)
	if err != nil {
		return VerifyResult{OK: false, Reason: "canonical_message_error"}
	}

	canonicalDigest := sha256Sum([]byte(msg.Raw))
	expectedMAC := computeHMAC(secret, msg.Raw)
	provided, err := hex.DecodeString(sigHex)
	if err != nil {
		return VerifyResult{OK: false, Reason: "invalid_signature_encoding"}
	}
	if subtle.ConstantTimeCompare(expectedMAC, provided) != 1 {
		return VerifyResult{OK: false, Reason: "signature_mismatch", CanonicalDigest: canonicalDigest}
	}

	return VerifyResult{
		OK:               true,
		Reason:           "allow",
		SignatureVersion: version,
		CacheHit:         cacheHit,
		AuthorityDigest:  key.AuthorityDigest,
		CanonicalDigest:  canonicalDigest,
	}
}

func computeHMAC(secret []byte, message string) []byte {
	m := hmac.New(sha256.New, secret)
	m.Write([]byte(message))
	return m.Sum(nil)
}

func sha256Sum(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func Sign(secret []byte, message string) string {
	return hex.EncodeToString(computeHMAC(secret, message))
}

func FormatSignatureHeader(version int, sigHex string) string {
	if version == 1 {
		return "v1 " + sigHex
	}
	return "v2 " + sigHex
}

func ParseSignatureHeader(h string) (version int, sig string, err error) {
	parts := strings.SplitN(h, " ", 2)
	if len(parts) != 2 {
		return 0, "", fmt.Errorf("malformed")
	}
	switch parts[0] {
	case "v1":
		return 1, parts[1], nil
	case "v2":
		return 2, parts[1], nil
	default:
		return 0, "", fmt.Errorf("unknown version")
	}
}
