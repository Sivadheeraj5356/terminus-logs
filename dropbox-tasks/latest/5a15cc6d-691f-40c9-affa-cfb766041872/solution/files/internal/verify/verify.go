package verify

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"os"
	"strings"

	"siggate/internal/canonical"
	"siggate/internal/model"
	"siggate/internal/profile"
)

func DecodeKey(b64 string) ([]byte, error) {
	return base64.StdEncoding.DecodeString(b64)
}

func MAC(key []byte, profileRaw []byte, canonicalRequest string) string {
	mac := hmac.New(sha256.New, key)
	mac.Write(profileRaw)
	mac.Write([]byte{0})
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
	if now > expires {
		return fmt.Errorf("expired")
	}
	return nil
}

func headerValue(headers map[string]string, name string) (string, bool) {
	for k, v := range headers {
		if strings.EqualFold(k, name) {
			return v, true
		}
	}
	return "", false
}

func ReplayID(kid string, created int64, mac string) string {
	return fmt.Sprintf("%s|%d|%s", kid, created, mac)
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
		if line == identity {
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

func trimOWS(s string, mask byte) string {
	runes := []rune(s)
	is := func(r rune) bool {
		switch r {
		case ' ':
			return mask&profile.OWSSp != 0
		case '\t':
			return mask&profile.OWSHtab != 0
		case '\u00a0':
			return mask&profile.OWSNbsp != 0
		default:
			return false
		}
	}
	start := 0
	for start < len(runes) && is(runes[start]) {
		start++
	}
	end := len(runes)
	for end > start && is(runes[end-1]) {
		end--
	}
	return string(runes[start:end])
}

func Envelope(env model.Envelope, keyring model.Keyring, now int64, seenPath string, prof profile.Profile) (string, error) {
	if env.Headers == nil {
		env.Headers = map[string]string{}
	}

	faults := map[byte]error{}

	keyB64, kidOK := keyring.Keys[env.Kid]
	if !kidOK {
		faults[profile.CodeUnknownKid] = fmt.Errorf("unknown_kid")
	}
	var key []byte
	if kidOK {
		var err error
		key, err = DecodeKey(keyB64)
		if err != nil {
			return "", fmt.Errorf("keyring_invalid")
		}
	}

	if err := CheckTime(now, env.Created, env.Expires); err != nil {
		faults[profile.CodeTime] = err
	}

	cr, cd, canonErr := canonical.Request(env, prof.OWSMask, prof.DigestMode)
	if canonErr != nil {
		if canonErr.Error() == "missing_covered_header" {
			faults[profile.CodeMissingHdr] = canonErr
		} else {
			return "", canonErr
		}
	}

	if canonErr == nil {
		for _, name := range env.Covered {
			if !strings.EqualFold(name, "content-digest") {
				continue
			}
			raw, ok := headerValue(env.Headers, "content-digest")
			if !ok {
				faults[profile.CodeMissingHdr] = fmt.Errorf("missing_covered_header")
				break
			}
			if trimOWS(raw, prof.OWSMask) != cd {
				faults[profile.CodeBadDigest] = fmt.Errorf("bad_digest")
			}
			break
		}
	}

	macOK := false
	if key != nil && canonErr == nil {
		expect := MAC(key, prof.Raw, cr)
		if hmac.Equal([]byte(expect), []byte(env.MAC)) {
			macOK = true
		} else {
			faults[profile.CodeBadMAC] = fmt.Errorf("bad_mac")
		}
	}

	if macOK {
		id := ReplayID(env.Kid, env.Created, env.MAC)
		hit, err := SeenContains(seenPath, id)
		if err != nil {
			return "", err
		}
		if hit {
			faults[profile.CodeReplay] = fmt.Errorf("replay")
		}
	}

	for _, code := range prof.Order {
		if e, ok := faults[code]; ok {
			return "", e
		}
	}

	id := ReplayID(env.Kid, env.Created, env.MAC)
	if err := AppendSeen(seenPath, id); err != nil {
		return "", err
	}
	return fmt.Sprintf("ok kid=%s digest=%s\n", env.Kid, cd), nil
}
