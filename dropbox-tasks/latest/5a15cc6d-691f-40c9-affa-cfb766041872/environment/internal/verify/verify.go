package verify

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"os"
	"strings"

	"siggate/internal/model"
)

func DecodeKey(b64 string) ([]byte, error) {
	return base64.StdEncoding.DecodeString(b64)
}

func MAC(key []byte, canonicalRequest string) string {
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(canonicalRequest))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func CheckTime(now, created, expires int64) error {
	if expires < created {
		return fmt.Errorf("invalid_window")
	}
	if now < created {
		return fmt.Errorf("not_yet_valid")
	}
	if now >= expires {
		return fmt.Errorf("expired")
	}
	return nil
}

func ReplayID(kid string, created int64, mac string) string {
	return fmt.Sprintf("%s|%s", kid, mac)
}

func SeenContains(path, identity string) (bool, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, fmt.Errorf("io")
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if strings.Contains(line, identity) {
			return true, nil
		}
	}
	return false, nil
}

func AppendSeen(path, identity string) error {
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return fmt.Errorf("io")
	}
	defer f.Close()
	if _, err := f.WriteString(identity + "\n"); err != nil {
		return fmt.Errorf("io")
	}
	return nil
}

// Stub verifier: admits every envelope. Rebuild from /app/docs/.
func Envelope(env model.Envelope, keyring model.Keyring, now int64, seenPath string) (string, error) {
	_ = keyring
	_ = now
	_ = seenPath
	return fmt.Sprintf("ok kid=%s digest=stub\n", env.Kid), nil
}
