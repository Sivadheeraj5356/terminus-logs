package emit

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"sort"

	"linkenv/reg"
)

func Fingerprint(rows []reg.RowRec) string {
	type wire struct {
		P string `json:"p"`
		V string `json:"v"`
		C uint8  `json:"c"`
	}
	w := make([]wire, len(rows))
	for i, r := range rows {
		w[i] = wire{P: r.Prefix, V: r.Via, C: r.Class}
	}
	sort.Slice(w, func(i, j int) bool {
		if w[i].P != w[j].P {
			return w[i].P < w[j].P
		}
		return w[i].V < w[j].V
	})
	raw, _ := json.Marshal(w)
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}
