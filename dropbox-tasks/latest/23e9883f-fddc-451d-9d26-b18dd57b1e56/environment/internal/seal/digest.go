package seal

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math"
	"sort"
)

var nextMode = map[string]string{
	"M1": "M2",
	"M2": "M3",
	"M3": "M4",
	"M4": "M1",
}

func fmt6(v float64) string {
	r := math.Round(v*1e6) / 1e6
	if r == 0 {
		r = 0
	}
	return fmt.Sprintf("%.6f", r)
}

func scale(mode string, excit float64, stiff, damp, cpl, weights map[string]float64, locale string) float64 {
	n := nextMode[mode]
	return weights[locale] * excit * (stiff[mode]*damp[mode] + cpl[mode]*stiff[n]*damp[n])
}

func residual(c ModeCell, stiff, damp, cpl, weights map[string]float64) float64 {
	return (c.OmegaObs - c.OmegaRef) - scale(c.Mode, c.Excit, stiff, damp, cpl, weights, c.Locale)
}

func digestOf(cells []ModeCell, stiff, damp, cpl, weights map[string]float64) string {
	byPanel := map[string][]float64{}
	for _, c := range cells {
		byPanel[c.PanelID] = append(byPanel[c.PanelID], residual(c, stiff, damp, cpl, weights))
	}
	pids := make([]string, 0, len(byPanel))
	for p := range byPanel {
		pids = append(pids, p)
	}
	sort.Strings(pids)
	parts := make([]string, 0, len(pids))
	for _, pid := range pids {
		rs := byPanel[pid]
		chunks := make([]string, len(rs))
		for i, v := range rs {
			chunks[i] = fmt6(v)
		}
		parts = append(parts, pid+":"+joinComma(chunks))
	}
	sum := sha256.Sum256([]byte(joinPipe(parts)))
	return hex.EncodeToString(sum[:])
}

func chainDigest(full, perm, rev, compose string) string {
	blob := full + "|" + perm + "|" + rev + "|" + compose
	sum := sha256.Sum256([]byte(blob))
	return hex.EncodeToString(sum[:])
}

func epochBindHex(clockRaw []byte, tableHash string) string {
	sum := sha256.Sum256(append(append(clockRaw, '|'), []byte(tableHash)...))
	return hex.EncodeToString(sum[:])
}

func joinComma(xs []string) string {
	out := ""
	for i, x := range xs {
		if i > 0 {
			out += ","
		}
		out += x
	}
	return out
}

func joinPipe(xs []string) string {
	out := ""
	for i, x := range xs {
		if i > 0 {
			out += "|"
		}
		out += x
	}
	return out
}

func rotateModeMap(m map[string]float64) map[string]float64 {
	// inverse rotate for permute_modes: M1<-M4, M2<-M1, M3<-M2, M4<-M3
	return map[string]float64{
		"M1": m["M4"],
		"M2": m["M1"],
		"M3": m["M2"],
		"M4": m["M3"],
	}
}

func permuteCells(cells []ModeCell) []ModeCell {
	mapping := map[string]string{"M1": "M2", "M2": "M3", "M3": "M4", "M4": "M1"}
	out := make([]ModeCell, len(cells))
	for i, c := range cells {
		n := c
		n.Mode = mapping[c.Mode]
		out[i] = n
	}
	return out
}

func reverseWeights(weights map[string]float64) map[string]float64 {
	keys := make([]string, 0, len(weights))
	for k := range weights {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	vals := make([]float64, len(keys))
	for i, k := range keys {
		vals[i] = weights[k]
	}
	for i, j := 0, len(vals)-1; i < j; i, j = i+1, j-1 {
		vals[i], vals[j] = vals[j], vals[i]
	}
	out := make(map[string]float64, len(keys))
	for i, k := range keys {
		out[k] = vals[i]
	}
	return out
}

func reverseCells(cells []ModeCell) []ModeCell {
	locales := map[string]struct{}{}
	for _, c := range cells {
		locales[c.Locale] = struct{}{}
	}
	keys := make([]string, 0, len(locales))
	for k := range locales {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	mapping := map[string]string{}
	for i := range keys {
		mapping[keys[i]] = keys[len(keys)-1-i]
	}
	out := make([]ModeCell, len(cells))
	for i, c := range cells {
		n := c
		n.Locale = mapping[c.Locale]
		out[i] = n
	}
	return out
}
