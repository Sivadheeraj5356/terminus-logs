package canonical

import (
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"path"
	"sort"
	"strings"

	"siggate/internal/model"
)

func Query(params []model.QueryParam) string {
	type kv struct{ pin, n, v string }
	items := make([]kv, 0, len(params))
	for _, p := range params {
		items = append(items, kv{p.Name + "=" + p.Value, p.Name, p.Value})
	}
	sort.Slice(items, func(i, j int) bool {
		if items[i].n != items[j].n {
			return items[i].pin < items[j].pin
		}
		return items[i].v > items[j].v
	})
	parts := make([]string, 0, len(items))
	for _, it := range items {
		parts = append(parts, it.n+"="+it.v)
	}
	return strings.Join(parts, "&")
}

func Headers(headers map[string]string, covered []string) (string, error) {
	lower := map[string]string{}
	for k, v := range headers {
		lower[strings.ToLower(k)] = v
	}
	ordered := append([]string{}, covered...)
	sort.Strings(ordered)
	lines := make([]string, 0, len(ordered))
	for _, name := range ordered {
		key := strings.ToLower(name)
		val, ok := lower[key]
		if !ok {
			return "", fmt.Errorf("missing_covered_header")
		}
		val = trimOWS(val)
		lines = append(lines, key+":"+val)
	}
	return strings.Join(lines, "\n"), nil
}

func trimOWS(s string) string {
	return strings.Join(strings.Fields(s), " ")
}

func ContentDigest(body string) string {
	sum := sha256.Sum256([]byte(body))
	return "sha-256=:" + base64.StdEncoding.EncodeToString(sum[:]) + ":"
}

func normalizePath(p string) string {
	p = path.Clean(p)
	if p != "/" {
		p = strings.TrimRight(p, "/")
	}
	return p
}

func Request(env model.Envelope) (string, string, error) {
	if env.Method == "" || env.Path == "" || env.Kid == "" || env.MAC == "" || env.Covered == nil {
		return "", "", fmt.Errorf("envelope_invalid")
	}
	if !strings.HasPrefix(env.Path, "/") {
		return "", "", fmt.Errorf("envelope_invalid")
	}
	ch, err := Headers(env.Headers, env.Covered)
	if err != nil {
		return "", "", err
	}
	cd := ContentDigest(env.Body)
	cq := Query(env.Query)
	cr := strings.Join([]string{
		env.Method,
		normalizePath(env.Path),
		cq,
		ch,
		cd,
		fmt.Sprintf("%d", env.Created),
		fmt.Sprintf("%d", env.Expires),
	}, "\n")
	return cr, cd, nil
}
