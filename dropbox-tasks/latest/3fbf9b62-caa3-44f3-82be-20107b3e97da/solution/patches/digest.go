package digest

import (
	"crypto/sha256"
	"encoding/hex"

	"modgate/internal/models"
)

func boolStr(v bool) string {
	if v {
		return "true"
	}
	return "false"
}

func Of(rows []models.IntegrityRow) string {
	h := sha256.New()
	for _, row := range rows {
		h.Write([]byte(row.ModID))
		h.Write([]byte(row.Member))
		h.Write([]byte(row.Linkage))
		h.Write([]byte(boolStr(row.Retracted)))
		h.Write([]byte(boolStr(row.ChecksumOK)))
		h.Write([]byte(boolStr(row.GoFloorOK)))
		h.Write([]byte(boolStr(row.Excluded)))
		h.Write([]byte(row.GateAction))
		h.Write([]byte(row.PolicyBasis))
	}
	return hex.EncodeToString(h.Sum(nil))
}

func RowDigest(row models.IntegrityRow) string {
	h := sha256.New()
	h.Write([]byte(row.ModID))
	h.Write([]byte(row.Member))
	h.Write([]byte(row.Linkage))
	h.Write([]byte(boolStr(row.Retracted)))
	h.Write([]byte(boolStr(row.ChecksumOK)))
	h.Write([]byte(boolStr(row.GoFloorOK)))
	h.Write([]byte(row.GateAction))
	h.Write([]byte(row.PolicyBasis))
	h.Write([]byte(row.LiveHash))
	return hex.EncodeToString(h.Sum(nil))
}

func ExportDigest(rows []models.IntegrityRow) (string, []models.PinDigest) {
	pins := make([]models.PinDigest, 0, len(rows))
	h := sha256.New()
	for _, row := range rows {
		rd := RowDigest(row)
		pins = append(pins, models.PinDigest{ModID: row.ModID, RowDigest: rd})
		h.Write([]byte(rd))
	}
	return hex.EncodeToString(h.Sum(nil)), pins
}

func MemberRollups(rows []models.IntegrityRow) []models.MemberRollup {
	order := make([]string, 0)
	seen := map[string]bool{}
	by := map[string][]models.IntegrityRow{}
	for _, row := range rows {
		if !seen[row.Member] {
			seen[row.Member] = true
			order = append(order, row.Member)
		}
		by[row.Member] = append(by[row.Member], row)
	}
	sortStrings(order)
	out := make([]models.MemberRollup, 0, len(order))
	for _, member := range order {
		pins := by[member]
		status := "pass"
		for _, row := range pins {
			if row.GateAction == "block" {
				status = "block"
				break
			}
			if row.GateAction == "warn" && status == "pass" {
				status = "warn"
			}
		}
		out = append(out, models.MemberRollup{
			Member:     member,
			PinCount:   len(pins),
			GateStatus: status,
		})
	}
	return out
}

func sortStrings(vals []string) {
	for i := 0; i < len(vals); i++ {
		for j := i + 1; j < len(vals); j++ {
			if vals[j] < vals[i] {
				vals[i], vals[j] = vals[j], vals[i]
			}
		}
	}
}
