package hashx

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"sort"

	"pitctl/types"
)

func canon(v any) string {
	switch t := v.(type) {
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		out := "{"
		for i, k := range keys {
			if i > 0 {
				out += ","
			}
			kb, _ := json.Marshal(k)
			out += string(kb) + ":" + canon(t[k])
		}
		return out + "}"
	case map[string]float64:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		m := map[string]any{}
		for _, k := range keys {
			m[k] = t[k]
		}
		return canon(m)
	case []any:
		out := "["
		for i, item := range t {
			if i > 0 {
				out += ","
			}
			out += canon(item)
		}
		return out + "]"
	case []string:
		arr := make([]any, 0, len(t))
		for _, s := range t {
			arr = append(arr, s)
		}
		return canon(arr)
	default:
		b, _ := json.Marshal(t)
		return string(b)
	}
}

func sortedValues(values map[string]float64) map[string]float64 {
	keys := make([]string, 0, len(values))
	for k := range values {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	out := map[string]float64{}
	for _, k := range keys {
		out[k] = values[k]
	}
	return out
}

func FeatHash(entity, revID string, values map[string]float64) string {
	payload := map[string]any{"entity": entity, "rev": revID, "values": sortedValues(values)}
	sum := sha256.Sum256([]byte(canon(payload)))
	return hex.EncodeToString(sum[:])
}

func rowToAny(r types.RowOut) map[string]any {
	return map[string]any{
		"event_id": r.EventID, "entity_id": r.EntityID, "feat_rev": r.FeatRev,
		"feat_hash": r.FeatHash, "asof_ms": r.AsofMs, "values": sortedValues(r.Values),
	}
}

func RowSeg(r types.RowOut) string {
	sum := sha256.Sum256([]byte(canon(rowToAny(r))))
	return hex.EncodeToString(sum[:])
}

func RowSegs(rows []types.RowOut) []string {
	ordered := append([]types.RowOut{}, rows...)
	sort.Slice(ordered, func(i, j int) bool { return ordered[i].EventID < ordered[j].EventID })
	out := make([]string, 0, len(ordered))
	for _, r := range ordered {
		out = append(out, RowSeg(r))
	}
	return out
}

func LedgerFromSegs(foldID string, segs []string) string {
	arr := make([]any, 0, len(segs))
	for _, s := range segs {
		arr = append(arr, s)
	}
	payload := map[string]any{"fold_id": foldID, "segs": arr}
	sum := sha256.Sum256([]byte(canon(payload)))
	return hex.EncodeToString(sum[:])
}

func LedgerDigest(foldID string, rows []types.RowOut) string {
	return LedgerFromSegs(foldID, RowSegs(rows))
}
