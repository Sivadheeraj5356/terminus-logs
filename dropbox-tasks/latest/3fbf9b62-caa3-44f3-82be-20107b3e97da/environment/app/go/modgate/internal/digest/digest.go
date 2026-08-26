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
		h.Write([]byte(boolStr(row.Retracted)))
		h.Write([]byte(boolStr(row.ChecksumOK)))
		h.Write([]byte(row.GateAction))
		h.Write([]byte(row.PolicyBasis))
	}
	return hex.EncodeToString(h.Sum(nil))
}

func RowDigest(row models.IntegrityRow) string {
	h := sha256.New()
	h.Write([]byte(row.ModID))
	h.Write([]byte(row.GateAction))
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
