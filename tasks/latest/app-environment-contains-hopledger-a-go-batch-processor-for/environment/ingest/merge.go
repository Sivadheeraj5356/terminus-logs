package ingest

import (
	"fmt"
	"sort"

	"github.com/terminus/hopledger/digest"
)

func kindRank(kind string) int {
	switch kind {
	case "checkpoint":
		return 0
	case "policy_update":
		return 1
	case "quarantine":
		return 2
	case "clear_quarantine":
		return 3
	case "link_close":
		return 4
	case "hop":
		return 5
	case "link_open":
		return 6
	case "note":
		return 7
	default:
		return 99
	}
}

func mergeKey(rec Record) [7]interface{} {
	return [7]interface{}{
		fmt.Sprintf("%05d", rec.Epoch),
		rec.Seq,
		kindRank(rec.Kind),
		rec.Raw.Priority,
		rec.Raw.Lane,
		rec.Raw.LineNum,
		rec.Raw.RawHash,
	}
}

func lessRecord(a, b Record) bool {
	ka, kb := mergeKey(a), mergeKey(b)
	for i := 0; i < 7; i++ {
		switch va := ka[i].(type) {
		case int:
			vb := kb[i].(int)
			if va != vb {
				return va < vb
			}
		case string:
			vb := kb[i].(string)
			if va != vb {
				return va < vb
			}
		}
	}
	return false
}

func ComputeRawInputDigest(rawLines []RawLine) string {
	payload := make([]map[string]interface{}, len(rawLines))
	for i, rl := range rawLines {
		payload[i] = map[string]interface{}{
			"lane":     rl.Lane,
			"priority": rl.Priority,
			"line":     rl.LineNum,
			"raw":      rl.Raw,
		}
	}
	return digest.SHA256Canonical(payload)
}

func BuildRecords(rawLines []RawLine) ([]Record, error) {
	records := make([]Record, 0, len(rawLines))
	for _, rl := range rawLines {
		defaultSource := rl.Lane
		if defaultSource == "" {
			defaultSource = "main"
		}
		rec, err := ParseEvent(rl, defaultSource)
		if err != nil {
			return nil, err
		}
		records = append(records, rec)
	}
	sort.Slice(records, func(i, j int) bool {
		return lessRecord(records[i], records[j])
	})
	for i := range records {
		records[i].MergeIndex = i
	}
	return records, nil
}

func SelectWinners(records []Record) map[IdentityKey]Record {
	winners := make(map[IdentityKey]Record)
	for _, rec := range records {
		key := Identity(rec)
		cur, ok := winners[key]
		if !ok || rec.Rev > cur.Rev || (rec.Rev == cur.Rev && rec.MergeIndex > cur.MergeIndex) {
			winners[key] = rec
		}
	}
	return winners
}
