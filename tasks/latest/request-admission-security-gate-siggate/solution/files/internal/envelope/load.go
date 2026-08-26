package envelope

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"

	"siggate/internal/model"
)

func decodeStrict(data []byte, dest any, invalid string) error {
	dec := json.NewDecoder(bytes.NewReader(data))
	if err := dec.Decode(dest); err != nil {
		return fmt.Errorf("%s", invalid)
	}
	// Reject any trailing non-whitespace JSON content after the first value.
	if err := dec.Decode(&struct{}{}); err != io.EOF {
		return fmt.Errorf("%s", invalid)
	}
	return nil
}

func Load(path string) (model.Envelope, error) {
	var env model.Envelope
	if info, err := os.Stat(path); err == nil && info.IsDir() {
		return env, fmt.Errorf("envelope_invalid")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return env, fmt.Errorf("io")
	}
	if err := decodeStrict(data, &env, "envelope_invalid"); err != nil {
		return env, err
	}
	if env.Method == "" || env.Path == "" || env.Kid == "" || env.MAC == "" || env.Covered == nil || env.Headers == nil {
		return env, fmt.Errorf("envelope_invalid")
	}
	return env, nil
}

func LoadKeyring(path string) (model.Keyring, error) {
	var kr model.Keyring
	if info, err := os.Stat(path); err == nil && info.IsDir() {
		return kr, fmt.Errorf("keyring_invalid")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return kr, fmt.Errorf("io")
	}
	if err := decodeStrict(data, &kr, "keyring_invalid"); err != nil {
		return kr, err
	}
	if kr.Keys == nil {
		return kr, fmt.Errorf("keyring_invalid")
	}
	return kr, nil
}
