#!/bin/bash
set -euo pipefail

cat > /app/environment/p1_slice/bounds.go <<'GO'
package p1_slice

import "balance_lab/p9_types"

func SliceEras(rows []p9_types.ChronologyRow, gap int) []p9_types.EraSpan {
	if len(rows) == 0 {
		return nil
	}
	ordered := append([]p9_types.ChronologyRow(nil), rows...)
	for i := 0; i < len(ordered); i++ {
		for j := i + 1; j < len(ordered); j++ {
			if ordered[j].Seq < ordered[i].Seq {
				ordered[i], ordered[j] = ordered[j], ordered[i]
			}
		}
	}
	var eras []p9_types.EraSpan
	id := 0
	start := ordered[0].PatchID
	end := ordered[0].PatchID
	prev := ordered[0].Seq
	for _, row := range ordered[1:] {
		if row.Seq-prev > gap {
			eras = append(eras, p9_types.EraSpan{ID: id, StartPatch: start, EndPatch: end})
			id++
			start = row.PatchID
		}
		end = row.PatchID
		prev = row.Seq
	}
	eras = append(eras, p9_types.EraSpan{ID: id, StartPatch: start, EndPatch: end})
	return eras
}
GO

cat > /app/environment/p2_pick/share.go <<'GO'
package p2_pick

func PickShare(picks int, totalMatches int) float64 {
	if totalMatches <= 0 {
		return 0
	}
	return float64(picks) / float64(totalMatches)
}
GO

cat > /app/environment/p3_win/lower.go <<'GO'
package p3_win

import "math"

func WinLower(wins, picks int, z float64) float64 {
	if picks <= 0 {
		return 0
	}
	p := float64(wins) / float64(picks)
	z2 := z * z
	denom := 1.0 + z2/float64(picks)
	center := p + z2/(2.0*float64(picks))
	rad := z * math.Sqrt((p*(1.0-p)/float64(picks)) + (z2/(4.0*float64(picks)*float64(picks))))
	return (center - rad) / denom
}
GO

cat > /app/environment/p4_shift/diverge.go <<'GO'
package p4_shift

import "math"

func kl(p, m float64) float64 {
	if p <= 0 {
		return 0
	}
	return p * math.Log(p/m)
}

func ShiftScore(a, b map[string]float64, roster []string) float64 {
	js := 0.0
	for _, actor := range roster {
		pa := a[actor]
		pb := b[actor]
		pm := 0.5 * (pa + pb)
		if pm <= 0 {
			continue
		}
		js += 0.5*kl(pa, pm) + 0.5*kl(pb, pm)
	}
	return js
}
GO

cat > /app/environment/p5_div/entropy.go <<'GO'
package p5_div

import "math"

func NormEntropy(shares []float64) float64 {
	var positive []float64
	for _, s := range shares {
		if s > 0 {
			positive = append(positive, s)
		}
	}
	n := len(positive)
	if n <= 1 {
		return 0
	}
	h := 0.0
	for _, s := range positive {
		h -= s * math.Log(s)
	}
	return h / math.Log(float64(n))
}
GO

cat > /app/environment/p6_note/sign.go <<'GO'
package p6_note

func NoteTag(headline string, statDelta int) string {
	_ = headline
	if statDelta < 0 {
		return "nerf_pressure"
	}
	if statDelta > 0 {
		return "buff_pressure"
	}
	return "tune_flat"
}
GO

cat > /app/environment/p7_rank/order.go <<'GO'
package p7_rank

import "sort"

type Target struct {
	Actor string
	Score  float64
}

func RankTargets(roster []string, pickShares map[string]float64, eraDiversity float64, winLowers map[string]float64) []string {
	_ = winLowers
	var rows []Target
	for _, actor := range roster {
		share := pickShares[actor]
		rows = append(rows, Target{Actor: actor, Score: share * (1.0 - eraDiversity)})
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].Score == rows[j].Score {
			return rows[i].Actor < rows[j].Actor
		}
		return rows[i].Score > rows[j].Score
	})
	out := make([]string, len(rows))
	for i, row := range rows {
		out[i] = row.Actor
	}
	return out
}
GO

cat > /app/environment/p8_seal/digest.go <<'GO'
package p8_seal

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strings"
)

func ArchiveDigest(parts []string) string {
	sorted := append([]string(nil), parts...)
	sort.Strings(sorted)
	sum := sha256.Sum256([]byte(strings.Join(sorted, "\n")))
	return hex.EncodeToString(sum[:8])
}
GO

cat > /app/environment/p7_chain/eras.go <<'GO'
package p7_chain

import (
	"math"

	"balance_lab/p9_types"
)

func BuildEras(rows []p9_types.ChronologyRow, matches []p9_types.MatchRow, roster []string, gap int, z float64) []p9_types.EraOut {
	spans := eraSpans(rows, gap)
	out := make([]p9_types.EraOut, 0, len(spans))
	for _, era := range spans {
		totals := eraTotals(era, rows, matches)
		totalPicks := 0
		for _, actor := range roster {
			totalPicks += totals[actor].Picks
		}
		var shares []float64
		dominant := roster[0]
		bestShare := -1.0
		for _, actor := range roster {
			picks := totals[actor].Picks
			share := actorShare(picks, totalPicks)
			if picks > 0 {
				shares = append(shares, share)
			}
			if share > bestShare {
				bestShare = share
				dominant = actor
			}
		}
		domWins := totals[dominant].Wins
		domPicks := totals[dominant].Picks
		out = append(out, p9_types.EraOut{
			ID:               era.ID,
			StartPatch:       era.StartPatch,
			EndPatch:         era.EndPatch,
			DominantActor:    dominant,
			DiversityIndex:   math.Round(eraDiversity(shares)*10000) / 10000,
			DominantWinLower: math.Round(actorWinLower(domWins, domPicks, z)*10000) / 10000,
		})
	}
	return out
}
GO

cat > /app/environment/p7_chain/recommend.go <<'GO'
package p7_chain

import "balance_lab/p9_types"

func BuildRecommendations(lastEra p9_types.EraSpan, rows []p9_types.ChronologyRow, matches []p9_types.MatchRow, notes []p9_types.NoteRow, roster []string, z float64) []p9_types.Recommendation {
	totals := eraTotals(lastEra, rows, matches)
	totalPicks := 0
	for _, actor := range roster {
		totalPicks += totals[actor].Picks
	}
	shares := map[string]float64{}
	var positive []float64
	for _, actor := range roster {
		picks := totals[actor].Picks
		share := actorShare(picks, totalPicks)
		shares[actor] = share
		if picks > 0 {
			positive = append(positive, share)
		}
	}
	diversity := eraDiversity(positive)
	winLowers := map[string]float64{}
	for _, actor := range roster {
		winLowers[actor] = actorWinLower(totals[actor].Wins, totals[actor].Picks, z)
	}
	ranked := rankedActors(roster, shares, diversity, winLowers)
	out := make([]p9_types.Recommendation, len(ranked))
	for i, actor := range ranked {
		out[i] = p9_types.Recommendation{
			Actor:        actor,
			Priority:     i + 1,
			RationaleTag: actorRationale(actor, notes, rows),
		}
	}
	return out
}
GO

cat > /app/environment/p7_chain/turning.go <<'GO'
package p7_chain

import (
	"math"

	"balance_lab/p9_types"
)

func patchVector(patchID string, matches []p9_types.MatchRow, roster []string) map[string]float64 {
	totals := map[string]int{}
	for _, actor := range roster {
		totals[actor] = 0
	}
	total := 0
	for _, row := range matches {
		if row.PatchID != patchID {
			continue
		}
		totals[row.Actor] += row.Picks
		total += row.Picks
	}
	vec := map[string]float64{}
	for _, actor := range roster {
		vec[actor] = actorShare(totals[actor], total)
	}
	return vec
}

func BuildTurningPoints(rows []p9_types.ChronologyRow, matches []p9_types.MatchRow, roster []string, threshold float64) []p9_types.TurningPoint {
	ordered := append([]p9_types.ChronologyRow(nil), rows...)
	for i := 0; i < len(ordered); i++ {
		for j := i + 1; j < len(ordered); j++ {
			if ordered[j].Seq < ordered[i].Seq {
				ordered[i], ordered[j] = ordered[j], ordered[i]
			}
		}
	}
	var points []p9_types.TurningPoint
	for i := 0; i < len(ordered)-1; i++ {
		va := patchVector(ordered[i].PatchID, matches, roster)
		vb := patchVector(ordered[i+1].PatchID, matches, roster)
		score := shiftBetween(va, vb, roster)
		if score >= threshold {
			points = append(points, p9_types.TurningPoint{
				PatchID:    ordered[i+1].PatchID,
				ShiftScore: math.Round(score*10000) / 10000,
			})
		}
	}
	if points == nil {
		return []p9_types.TurningPoint{}
	}
	return points
}
GO

make -C /app/environment all
