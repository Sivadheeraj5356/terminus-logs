package keyring

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
)

func Load(path string) (*Keyring, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read keyring: %w", err)
	}
	var kr Keyring
	if err := json.Unmarshal(data, &kr); err != nil {
		return nil, fmt.Errorf("parse keyring: %w", err)
	}
	for i := range kr.Keys {
		k := &kr.Keys[i]
		if k.Secret == nil && k.SecretHex != "" {
			sec, err := hex.DecodeString(k.SecretHex)
			if err != nil {
				return nil, fmt.Errorf("decode secret for %s: %w", k.KeyID, err)
			}
			k.Secret = sec
		}
	}
	return &kr, nil
}
