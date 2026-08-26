package audit

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"sort"
)

// OverallChainTip folds every stream's chain_tip_hash into one summary value,
// so a caller can tell whether anything in the whole database changed with a
// single comparison instead of walking every stream.
func OverallChainTip(streams []StreamVerifyReport) string {
	sorted := make([]StreamVerifyReport, len(streams))
	copy(sorted, streams)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].StreamID < sorted[j].StreamID })

	h := sha256.New()
	for _, s := range sorted {
		tipBytes, _ := hex.DecodeString(s.ChainTipHash)
		var idLen [2]byte
		binary.BigEndian.PutUint16(idLen[:], uint16(len(s.StreamID)))
		h.Write(idLen[:])
		h.Write([]byte(s.StreamID))
		h.Write(tipBytes)
	}
	return hex.EncodeToString(h.Sum(nil))
}
