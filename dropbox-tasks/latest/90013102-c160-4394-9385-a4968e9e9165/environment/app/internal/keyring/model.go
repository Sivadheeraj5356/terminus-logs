package keyring

import (
	"crypto/sha256"
	"encoding/hex"
)

type Key struct {
	Tenant           string   `json:"tenant"`
	KeyID            string   `json:"key_id"`
	KeyEpoch         int      `json:"key_epoch"`
	Secret           []byte   `json:"secret"`
	SecretHex        string   `json:"secret_hex"`
	AllowedProfiles  []string `json:"allowed_profiles"`
	AllowedVersions  []int    `json:"allowed_versions"`
	Revoked          bool     `json:"revoked"`
	AuthorityDigest  string   `json:"authority_digest"`
}

type Keyring struct {
	Keys []Key `json:"keys"`
}

func (kr *Keyring) Lookup(tenant, keyID string, epoch int) (*Key, bool) {
	for i := range kr.Keys {
		k := &kr.Keys[i]
		if k.Tenant == tenant && k.KeyID == keyID && k.KeyEpoch == epoch {
			if k.Secret == nil && k.SecretHex != "" {
				sec, err := hex.DecodeString(k.SecretHex)
				if err == nil {
					k.Secret = sec
				}
			}
			if k.AuthorityDigest == "" {
				k.AuthorityDigest = computeAuthorityDigest(k)
			}
			return k, true
		}
	}
	return nil, false
}

func computeAuthorityDigest(k *Key) string {
	h := sha256.New()
	h.Write([]byte(k.Tenant))
	h.Write([]byte{0})
	h.Write([]byte(k.KeyID))
	h.Write([]byte{0})
	for _, p := range k.AllowedProfiles {
		h.Write([]byte(p))
		h.Write([]byte{0})
	}
	sum := h.Sum(nil)
	return hex.EncodeToString(sum)
}
