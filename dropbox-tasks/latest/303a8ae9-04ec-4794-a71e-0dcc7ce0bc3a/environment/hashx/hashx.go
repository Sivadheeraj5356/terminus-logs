package hashx

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"

	"pitctl/types"
)

func FeatHash(entity, revID string, values map[string]float64) string {
	_ = entity
	b, _ := json.Marshal(map[string]any{"rev": revID, "values": values})
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func RowSeg(r types.RowOut) string {
	b, _ := json.Marshal(r)
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func RowSegs(rows []types.RowOut) []string {
	out := make([]string, 0, len(rows))
	for _, r := range rows {
		out = append(out, RowSeg(r))
	}
	return out
}

func LedgerFromSegs(foldID string, segs []string) string {
	b, _ := json.Marshal(map[string]any{"fold_id": foldID, "segs": segs})
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func LedgerDigest(foldID string, rows []types.RowOut) string {
	b, _ := json.Marshal(map[string]any{"fold_id": foldID, "rows": rows})
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}
