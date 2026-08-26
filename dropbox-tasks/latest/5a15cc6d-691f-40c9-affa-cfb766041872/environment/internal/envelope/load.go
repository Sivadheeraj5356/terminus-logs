package envelope

import (
	"encoding/json"
	"fmt"
	"os"

	"siggate/internal/model"
)

func Load(path string) (model.Envelope, error) {
	var env model.Envelope
	data, err := os.ReadFile(path)
	if err != nil {
		return env, fmt.Errorf("io")
	}
	if err := json.Unmarshal(data, &env); err != nil {
		return env, fmt.Errorf("envelope_invalid")
	}
	if env.Method == "" || env.Path == "" || env.Kid == "" || env.MAC == "" || env.Covered == nil || env.Headers == nil {
		return env, fmt.Errorf("envelope_invalid")
	}
	return env, nil
}

func LoadKeyring(path string) (model.Keyring, error) {
	var kr model.Keyring
	data, err := os.ReadFile(path)
	if err != nil {
		return kr, fmt.Errorf("io")
	}
	if err := json.Unmarshal(data, &kr); err != nil {
		return kr, fmt.Errorf("keyring_invalid")
	}
	if kr.Keys == nil {
		return kr, fmt.Errorf("keyring_invalid")
	}
	return kr, nil
}
