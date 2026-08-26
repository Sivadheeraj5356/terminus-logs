package codec

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
)

func CanonicalJSON(v any) ([]byte, error) {
	normalized, err := normalize(v)
	if err != nil {
		return nil, err
	}
	return marshalSorted(normalized)
}

func DigestHex(v any) (string, error) {
	raw, err := CanonicalJSON(v)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), nil
}

func normalize(v any) (any, error) {
	switch t := v.(type) {
	case map[string]any:
		out := make(map[string]any, len(t))
		for k, val := range t {
			n, err := normalize(val)
			if err != nil {
				return nil, err
			}
			out[k] = n
		}
		return out, nil
	case []any:
		out := make([]any, len(t))
		for i, val := range t {
			n, err := normalize(val)
			if err != nil {
				return nil, err
			}
			out[i] = n
		}
		return out, nil
	default:
		return t, nil
	}
}

func marshalSorted(v any) ([]byte, error) {
	switch t := v.(type) {
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		var buf bytes.Buffer
		buf.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				buf.WriteByte(',')
			}
			keyJSON, err := json.Marshal(k)
			if err != nil {
				return nil, err
			}
			buf.Write(keyJSON)
			buf.WriteByte(':')
			valJSON, err := marshalSorted(t[k])
			if err != nil {
				return nil, err
			}
			buf.Write(valJSON)
		}
		buf.WriteByte('}')
		return buf.Bytes(), nil
	case []any:
		var buf bytes.Buffer
		buf.WriteByte('[')
		for i, item := range t {
			if i > 0 {
				buf.WriteByte(',')
			}
			valJSON, err := marshalSorted(item)
			if err != nil {
				return nil, err
			}
			buf.Write(valJSON)
		}
		buf.WriteByte(']')
		return buf.Bytes(), nil
	case string:
		return json.Marshal(t)
	case bool:
		if t {
			return []byte("true"), nil
		}
		return []byte("false"), nil
	case float64:
		return []byte(fmt.Sprintf("%v", t)), nil
	case int:
		return []byte(fmt.Sprintf("%d", t)), nil
	case int64:
		return []byte(fmt.Sprintf("%d", t)), nil
	case nil:
		return []byte("null"), nil
	default:
		return json.Marshal(t)
	}
}

func LockDigestBody(generatedFrom string, attemptCount, failureTotal, eventLineCount, appliedCount, rejectedCount int, projectionDigest string, views, audits []map[string]any) (string, error) {
	body := map[string]any{
		"generated_from":    generatedFrom,
		"attempt_count":     attemptCount,
		"failure_total":     failureTotal,
		"event_line_count":  eventLineCount,
		"applied_count":     appliedCount,
		"rejected_count":    rejectedCount,
		"projection_digest": projectionDigest,
		"views":             views,
		"audits":            audits,
	}
	return DigestHex(body)
}

func AuditDigestBody(generatedFrom string, batchCount int, journalDigest, projectionDigest string, batches []map[string]any) (string, error) {
	body := map[string]any{
		"generated_from":    generatedFrom,
		"batch_count":       batchCount,
		"journal_digest":    journalDigest,
		"projection_digest": projectionDigest,
		"batches":           batches,
	}
	return DigestHex(body)
}
