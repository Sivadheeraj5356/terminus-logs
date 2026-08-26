package r3

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strconv"
	"strings"

	"fxdesk/internal/model"
)

func Assemble(doc *model.SyncRecord, g1Prefix, g2Prefix string, crossSeed uint32) {
	emit_d(doc, g1Prefix, g2Prefix, crossSeed)
}

func emit_d(doc *model.SyncRecord, g1Prefix, g2Prefix string, crossSeed uint32) {
	if g1Prefix != "" && g2Prefix != "" {
		doc.CrossAadDigest = CrossAadHex(g1Prefix, g2Prefix, crossSeed)
	}
	doc.RecordDigest = RecordDigest(doc)
}

func RowHex(grp int, keyIdx int, aadHex string) string {
	buf := []byte(strconv.Itoa(grp) + "|" + strconv.Itoa(keyIdx) + "|" + aadHex)
	sum := sha256.Sum256(buf)
	return hex.EncodeToString(sum[:])[:12]
}

func CrossAadHex(a, b string, crossSeed uint32) string {
	payload := "G|" + a + "|" + b
	if crossSeed != 0 {
		payload += "|" + strconv.FormatUint(uint64(crossSeed), 10)
	}
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:])
}

func RecordDigest(doc *model.SyncRecord) string {
	var lines []string
	for _, row := range doc.BindRows {
		lines = append(lines, "B|"+strconv.FormatUint(uint64(row.Grp), 10)+"|"+strconv.FormatUint(uint64(row.KeyIdx), 10)+"|"+row.AadHex+"|"+row.RowHex)
	}
	if doc.CrossAadDigest != "" {
		lines = append(lines, "C|"+doc.CrossAadDigest)
	}
	if doc.PartSig != "" {
		lines = append(lines, "P|"+doc.PartSig)
	}
	meta := doc.RunMeta
	lines = append(lines, "M|"+meta.CaseID+"|"+meta.Phase)
	sort.Strings(lines)
	body := strings.Join(lines, "\n") + "\n"
	sum := sha256.Sum256([]byte(body))
	return hex.EncodeToString(sum[:])
}

func AadHex(aad []byte) string {
	return hex.EncodeToString(aad)
}
