package h2

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"
)

func ScoreHex(issuer, thisUp string, serials []string) string {
	cp := append([]string{}, serials...)
	sort.Strings(cp)
	payload := fmt.Sprintf("%s|%s|%s", issuer, thisUp, strings.Join(cp, ","))
	h := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(h[:8])
}

func LagCode(a, b string) int {
	if len(a) < 8 || len(b) < 8 {
		return 99
	}
	ai, _ := hex.DecodeString(a[:8])
	bi, _ := hex.DecodeString(b[:8])
	diff := 0
	for i := 0; i < 8 && i < len(ai) && i < len(bi); i++ {
		d := int(ai[i]) - int(bi[i])
		if d < 0 {
			d = -d
		}
		diff += d
	}
	return diff
}

func NcSkew(a, b string) int {
	return LagCode(a, b)
}

func BandHex(stamps []string) string {
	cp := append([]string{}, stamps...)
	sort.Strings(cp)
	h := sha256.Sum256([]byte(strings.Join(cp, "")))
	return hex.EncodeToString(h[:6])
}

func WitnessDigest(cycles []CycleResult) string {
	type tuple struct {
		tenant string
		mode   string
		dig    string
		span   int
	}
	var tuples []tuple
	for _, cycle := range cycles {
		tuples = append(tuples, tuple{cycle.ProfileID, cycle.PassMode, cycle.BandHex, cycle.CarrySpan})
	}
	sort.Slice(tuples, func(i, j int) bool {
		if tuples[i].tenant != tuples[j].tenant {
			return tuples[i].tenant < tuples[j].tenant
		}
		return tuples[i].mode < tuples[j].mode
	})
	var parts []string
	for _, t := range tuples {
		parts = append(parts, fmt.Sprintf("%s:%s:%s:%d", t.tenant, t.mode, t.dig, t.span))
	}
	h := sha256.Sum256([]byte(strings.Join(parts, "|")))
	return hex.EncodeToString(h[:8])
}
