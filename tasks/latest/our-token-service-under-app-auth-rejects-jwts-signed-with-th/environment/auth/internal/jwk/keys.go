package jwk

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type RotationState struct {
	ActiveKid    string `json:"active_kid"`
	RetiringKid  string `json:"retiring_kid"`
	RotatedAt    int64  `json:"rotated_at"`
	GraceSeconds int64  `json:"grace_seconds"`
}

type PublicKey struct {
	Kid string
	Key ed25519.PublicKey
}

type Set struct {
	keys map[string]ed25519.PublicKey
}

func LoadRotationState(path string) (*RotationState, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var state RotationState
	if err := json.Unmarshal(raw, &state); err != nil {
		return nil, err
	}
	return &state, nil
}

type jwkDoc struct {
	Kty string `json:"kty"`
	Crv string `json:"crv"`
	Kid string `json:"kid"`
	X   string `json:"x"`
}

func loadOne(path string) (PublicKey, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return PublicKey{}, err
	}
	var doc jwkDoc
	if err := json.Unmarshal(raw, &doc); err != nil {
		return PublicKey{}, err
	}
	pub, err := base64.RawURLEncoding.DecodeString(doc.X)
	if err != nil {
		return PublicKey{}, err
	}
	if len(pub) != ed25519.PublicKeySize {
		return PublicKey{}, fmt.Errorf("invalid ed25519 key size")
	}
	return PublicKey{Kid: doc.Kid, Key: ed25519.PublicKey(pub)}, nil
}

func LoadActiveOnly(keysDir string, state *RotationState) (*Set, error) {
	pk, err := loadOne(filepath.Join(keysDir, "jwk-active.json"))
	if err != nil {
		return nil, err
	}
	return &Set{keys: map[string]ed25519.PublicKey{state.ActiveKid: pk.Key}}, nil
}

func (s *Set) Lookup(kid string) (ed25519.PublicKey, bool) {
	k, ok := s.keys[kid]
	return k, ok
}

func LoadPublished(keysDir string, state *RotationState, nowUnix int64, configGrace int64) (*Set, error) {
	active, err := loadOne(filepath.Join(keysDir, "jwk-active.json"))
	if err != nil {
		return nil, err
	}
	keys := map[string]ed25519.PublicKey{state.ActiveKid: active.Key}
	graceEnd := state.RotatedAt + configGrace
	if nowUnix <= graceEnd {
		retiring, err := loadOne(filepath.Join(keysDir, "jwk-retiring.json"))
		if err != nil {
			return nil, err
		}
		keys[state.RetiringKid] = retiring.Key
	}
	return &Set{keys: keys}, nil
}
