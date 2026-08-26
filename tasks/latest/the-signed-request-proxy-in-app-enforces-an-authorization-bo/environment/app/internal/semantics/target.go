package semantics

import (
	"fmt"
	"net/url"
	"strings"
)

// Profile defines URI normalization rules for a signature profile.
type Profile struct {
	ID                    string
	Epoch                 int
	SignatureVersion      int
	PreserveLegacyQuery   bool
	UppercasePercent      bool
	RemoveDotSegments     bool
}

func NormalizeTarget(profile *Profile, rawTarget string) (path, query, canonical string, pairs []QueryPair, err error) {
	if rawTarget == "" {
		return "", "", "", nil, fmt.Errorf("empty target")
	}
	pathPart := rawTarget
	queryPart := ""
	if i := strings.Index(rawTarget, "?"); i >= 0 {
		pathPart = rawTarget[:i]
		queryPart = rawTarget[i+1:]
	}

	path, err = normalizePath(profile, pathPart)
	if err != nil {
		return "", "", "", nil, err
	}

	if profile.PreserveLegacyQuery {
		query = queryPart
		pairs = parseLegacyQuery(queryPart)
	} else {
		pairs, err = parseCurrentQuery(queryPart)
		if err != nil {
			return "", "", "", nil, err
		}
		query = encodeCurrentQuery(pairs)
	}

	canonical = path
	if query != "" {
		canonical = path + "?" + query
	}
	return path, query, canonical, pairs, nil
}

func normalizePath(profile *Profile, path string) (string, error) {
	if !strings.HasPrefix(path, "/") {
		return "", fmt.Errorf("path must be absolute")
	}
	decoded, err := decodePathSegments(path, profile.UppercasePercent)
	if err != nil {
		return "", err
	}
	if profile.RemoveDotSegments {
		decoded = removeDotSegments(decoded)
	}
	if profile.UppercasePercent {
		return encodePathUppercase(decoded), nil
	}
	return decoded, nil
}

func decodePathSegments(path string, uppercase bool) (string, error) {
	var b strings.Builder
	for i := 0; i < len(path); i++ {
		if path[i] != '%' {
			b.WriteByte(path[i])
			continue
		}
		if i+2 >= len(path) {
			return "", fmt.Errorf("malformed percent encoding")
		}
		hex := path[i+1 : i+3]
		if !isHex(hex[0]) || !isHex(hex[1]) {
			return "", fmt.Errorf("malformed percent encoding")
		}
		if uppercase {
			hex = strings.ToUpper(hex)
		}
		b.WriteByte('%')
		b.WriteString(hex)
		i += 2
	}
	return b.String(), nil
}

func encodePathUppercase(path string) string {
	var b strings.Builder
	for i := 0; i < len(path); i++ {
		if path[i] != '%' {
			b.WriteByte(path[i])
			continue
		}
		if i+2 < len(path) {
			b.WriteByte('%')
			b.WriteString(strings.ToUpper(path[i+1 : i+3]))
			i += 2
		}
	}
	return b.String()
}

func removeDotSegments(path string) string {
	if path == "" {
		return "/"
	}
	segments := strings.Split(path, "/")
	out := make([]string, 0, len(segments))
	for _, seg := range segments {
		switch seg {
		case "", ".":
			continue
		case "..":
			if len(out) > 0 {
				out = out[:len(out)-1]
			}
		default:
			out = append(out, seg)
		}
	}
	if len(out) == 0 {
		return "/"
	}
	return "/" + strings.Join(out, "/")
}

func parseCurrentQuery(q string) ([]QueryPair, error) {
	if q == "" {
		return nil, nil
	}
	vals, err := url.ParseQuery(q)
	if err != nil {
		return nil, err
	}
	pairs := make([]QueryPair, 0)
	for _, key := range sortedKeys(vals) {
		for _, v := range vals[key] {
			pairs = append(pairs, QueryPair{Key: key, Value: v})
		}
	}
	return pairs, nil
}

func parseLegacyQuery(q string) []QueryPair {
	if q == "" {
		return nil
	}
	parts := strings.Split(q, "&")
	pairs := make([]QueryPair, 0, len(parts))
	for _, part := range parts {
		key, val, _ := strings.Cut(part, "=")
		key, _ = url.QueryUnescape(key)
		val, _ = url.QueryUnescape(val)
		pairs = append(pairs, QueryPair{Key: key, Value: val})
	}
	return pairs
}

func encodeCurrentQuery(pairs []QueryPair) string {
	if len(pairs) == 0 {
		return ""
	}
	parts := make([]string, 0, len(pairs))
	for _, p := range pairs {
		parts = append(parts, url.QueryEscape(p.Key)+"="+url.QueryEscape(p.Value))
	}
	return strings.Join(parts, "&")
}

func sortedKeys(m url.Values) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	for i := 0; i < len(keys); i++ {
		for j := i + 1; j < len(keys); j++ {
			if keys[j] < keys[i] {
				keys[i], keys[j] = keys[j], keys[i]
			}
		}
	}
	return keys
}

func isHex(c byte) bool {
	return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F') || (c >= 'a' && c <= 'f')
}
