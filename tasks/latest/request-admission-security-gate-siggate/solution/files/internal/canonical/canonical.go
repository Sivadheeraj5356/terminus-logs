package canonical

import (
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"sort"
	"strings"

	"siggate/internal/model"
	"siggate/internal/profile"
)

func Query(params []model.QueryParam) string {
	type kv struct{ n, v string }
	items := make([]kv, 0, len(params))
	for _, p := range params {
		items = append(items, kv{p.Name, p.Value})
	}
	sort.Slice(items, func(i, j int) bool {
		if items[i].n != items[j].n {
			return items[i].n < items[j].n
		}
		return items[i].v < items[j].v
	})
	parts := make([]string, 0, len(items))
	for _, it := range items {
		parts = append(parts, it.n+"="+it.v)
	}
	return strings.Join(parts, "&")
}

func isOWS(r rune, mask byte) bool {
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

func trimOWS(s string, mask byte) string {
	runes := []rune(s)
	start := 0
	for start < len(runes) && isOWS(runes[start], mask) {
		start++
	}
	end := len(runes)
	for end > start && isOWS(runes[end-1], mask) {
		end--
	}
	return string(runes[start:end])
}

func Headers(headers map[string]string, covered []string, owsMask byte) (string, error) {
	lower := map[string]string{}
	for k, v := range headers {
		lower[strings.ToLower(k)] = v
	}
	lines := make([]string, 0, len(covered))
	for _, name := range covered {
		key := strings.ToLower(name)
		val, ok := lower[key]
		if !ok {
			return "", fmt.Errorf("missing_covered_header")
		}
		val = trimOWS(val, owsMask)
		lines = append(lines, key+":"+val)
	}
	return strings.Join(lines, "\n"), nil
}

func ContentDigest(body string, mode byte) string {
	sum := sha256.Sum256([]byte(body))
	switch mode {
	case profile.DigestBareStd:
		return "sha-256=" + base64.StdEncoding.EncodeToString(sum[:])
	case profile.DigestColonURL:
		return "sha-256=:" + base64.RawURLEncoding.EncodeToString(sum[:]) + ":"
	default:
		return "sha-256=:" + base64.StdEncoding.EncodeToString(sum[:]) + ":"
	}
}

func Request(env model.Envelope, owsMask, digestMode byte) (string, string, error) {
	if env.Method == "" || env.Path == "" || env.Kid == "" || env.MAC == "" || env.Covered == nil {
		return "", "", fmt.Errorf("envelope_invalid")
	}
	if !strings.HasPrefix(env.Path, "/") {
		return "", "", fmt.Errorf("envelope_invalid")
	}
	ch, err := Headers(env.Headers, env.Covered, owsMask)
	if err != nil {
		return "", "", err
	}
	cd := ContentDigest(env.Body, digestMode)
	cq := Query(env.Query)
	cr := strings.Join([]string{
		env.Method,
		env.Path,
		cq,
		ch,
		cd,
		fmt.Sprintf("%d", env.Created),
		fmt.Sprintf("%d", env.Expires),
	}, "\n")
	return cr, cd, nil
}
