package digest

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"sort"
)

func SHA256Canonical(v interface{}) string {
	raw := CanonicalJSON(v)
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}

func CanonicalJSON(v interface{}) string {
	canon := canonical(v)
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(canon)
	out := bytes.TrimRight(buf.Bytes(), "\n")
	return string(out)
}

func canonical(v interface{}) interface{} {
	switch val := v.(type) {
	case map[string]interface{}:
		keys := make([]string, 0, len(val))
		for k := range val {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		out := make(map[string]interface{}, len(val))
		for _, k := range keys {
			out[k] = canonical(val[k])
		}
		return out
	case []interface{}:
		out := make([]interface{}, len(val))
		for i, item := range val {
			out[i] = canonical(item)
		}
		return out
	default:
		return v
	}
}

func CanonicalizeStruct(v interface{}) (interface{}, error) {
	raw, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	var data interface{}
	if err := json.Unmarshal(raw, &data); err != nil {
		return nil, err
	}
	return canonical(data), nil
}

func ComputeDigest(report interface{}, rawInputDigest, policyLineageDigest string, audit []map[string]interface{}) string {
	payload := map[string]interface{}{
		"report":                 report,
		"raw_input_digest":         rawInputDigest,
		"policy_lineage_digest":  policyLineageDigest,
		"audit":                    audit,
	}
	return SHA256Canonical(payload)
}
