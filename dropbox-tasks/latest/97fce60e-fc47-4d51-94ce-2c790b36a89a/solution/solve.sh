#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/go/bin:/opt/verifier-venv/bin:/usr/bin:/bin:${PATH:-}"
export GOCACHE="${GOCACHE:-/app/out/.gocache}"
export GOTMPDIR="${GOTMPDIR:-/app/out/.gotmp}"

cd /app

# Read-only inspection of the broken implementation and rule manifest before repair.
for path in /app/faircore/*.go /app/rollbench/lootfair/main.go /app/dropvault/fairness_rules.json; do
  test -r "$path"
done
sed -n '1,120p' /app/faircore/evaluator.go >/dev/null
sed -n '1,80p' /app/faircore/gates.go >/dev/null
sed -n '1,40p' /app/dropvault/fairness_rules.json >/dev/null

cat > /app/faircore/replay.go <<'EOF'
package faircore

func NextRoll(state *int) float64 {
	rv := float64((*state>>16)&0x7FFF) / 32767.0
	*state = (1103515245*(*state) + 12345) % (1 << 31)
	return rv
}
EOF

cat > /app/faircore/selector.go <<'EOF'
package faircore

import "sort"

func SelectItem(rollValue float64, pool []PoolItem, pityTier string) PoolItem {
	sorted := append([]PoolItem(nil), pool...)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].ItemID < sorted[j].ItemID })
	if pityTier != "" {
		for _, p := range sorted {
			if p.Tier == pityTier {
				return p
			}
		}
	}
	total := 0
	for _, p := range sorted {
		total += p.Weight
	}
	if total == 0 {
		return sorted[0]
	}
	target := rollValue * float64(total)
	cum := 0
	for _, p := range sorted {
		cum += p.Weight
		if float64(cum) >= target {
			return p
		}
	}
	return sorted[len(sorted)-1]
}

func poolByID(pool []PoolItem) map[string]PoolItem {
	out := make(map[string]PoolItem)
	for _, p := range pool {
		out[p.ItemID] = p
	}
	return out
}

func tierWeights(pool []PoolItem) map[string]int {
	out := make(map[string]int)
	for _, p := range pool {
		out[p.Tier] += p.Weight
	}
	return out
}
EOF

cat > /app/faircore/metrics.go <<'EOF'
package faircore

import "sort"

func ComputeGini(counts map[string]int, players []string) float64 {
	vals := make([]int, 0, len(players))
	for _, p := range players {
		vals = append(vals, counts[p])
	}
	sort.Ints(vals)
	n := len(vals)
	if n == 0 {
		return 0
	}
	total := 0
	for _, v := range vals {
		total += v
	}
	if total == 0 {
		return 0
	}
	cum := 0
	num := 0
	for i, v := range vals {
		cum += v
		num += (i + 1) * v
	}
	return float64(2*num)/float64(n*total) - float64(n+1)/float64(n)
}

func populationVariance(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	sum := 0.0
	for _, v := range values {
		sum += v
	}
	mean := sum / float64(len(values))
	var acc float64
	for _, v := range values {
		d := v - mean
		acc += d * d
	}
	return acc / float64(len(values))
}

func round4(v float64) float64 {
	x := float64(int(v*10000+0.5)) / 10000
	if x == float64(int(x)) {
		return float64(int(x))
	}
	return x
}

func buildTierStats(session Session, tierCounts map[string]int) []TierStat {
	tw := tierWeights(session.LootPool)
	totalWeight := 0
	for _, w := range tw {
		totalWeight += w
	}
	n := len(session.Rolls)
	tiers := make([]string, 0, len(tw))
	for t := range tw {
		tiers = append(tiers, t)
	}
	sort.Strings(tiers)
	out := make([]TierStat, 0, len(tiers))
	for _, tier := range tiers {
		observed := tierCounts[tier]
		expected := 0.0
		if totalWeight > 0 {
			expected = float64(tw[tier]) / float64(totalWeight) * float64(n)
		}
		chi := 0.0
		if expected > 0 {
			diff := float64(observed) - expected
			chi = (diff * diff) / expected
		}
		out = append(out, TierStat{
			Tier:      tier,
			Observed:  observed,
			Expected:  round4(expected),
			ChiSquare: round4(chi),
		})
	}
	return out
}
EOF

cat > /app/faircore/evaluator.go <<'EOF'
package faircore

import (
	"fmt"
	"sort"
)

const (
	rngEps            = 1e-9
	chiThreshold      = 6.635
	giniThreshold     = 0.55
	varianceThreshold = 0.08
)

func findingID(sessionID, playerID, kind string, seq int) string {
	return fmt.Sprintf("%s::%s::%s::%04d", sessionID, playerID, kind, seq)
}

func appendFinding(findings *[]Finding, sessionID, playerID, kind, detail string, seq int) {
	*findings = append(*findings, Finding{
		FindingID: findingID(sessionID, playerID, kind, seq),
		PlayerID:  playerID,
		Kind:      kind,
		Detail:    detail,
		Seq:       seq,
	})
}

func AnalyzeSession(s Session) SessionOut {
	findings := make([]Finding, 0)
	byPlayer := make(map[string]int)
	epicByPlayer := make(map[string]int)
	naturalEpicByPlayer := make(map[string]int)
	tierCounts := make(map[string]int)
	poolMap := poolByID(s.LootPool)
	uniqueSeen := make(map[string]int)
	lastItemSeq := make(map[string]int)
	seenSeq := make(map[int]bool)
	recentValues := make([]float64, 0, 8)

	state := s.RNGSeed
	sincePity := 0
	streakTier := ""
	streakLen := 0
	rolls := append([]Roll(nil), s.Rolls...)
	sort.Slice(rolls, func(i, j int) bool { return rolls[i].Seq < rolls[j].Seq })

	for _, roll := range rolls {
		if seenSeq[roll.Seq] {
			appendFinding(&findings, s.SessionID, roll.PlayerID, "DUPLICATE_SEQ",
				fmt.Sprintf("%d", roll.Seq), roll.Seq)
			continue
		}
		seenSeq[roll.Seq] = true

		expected := NextRoll(&state)
		if abs(expected-roll.RollValue) > rngEps {
			appendFinding(&findings, s.SessionID, roll.PlayerID, "RNG_MISMATCH",
				fmt.Sprintf("%.12f", roll.RollValue), roll.Seq)
		}

		pityActive := sincePity >= s.PityThreshold
		pityTier := ""
		if pityActive {
			pityTier = s.PityTier
		}
		expectedItem := SelectItem(expected, s.LootPool, pityTier)
		if pityActive && roll.ItemID != expectedItem.ItemID {
			appendFinding(&findings, s.SessionID, roll.PlayerID, "PITY_VIOLATION", expectedItem.ItemID, roll.Seq)
		}

		item, inPool := poolMap[roll.ItemID]
		if !inPool {
			appendFinding(&findings, s.SessionID, roll.PlayerID, "POOL_MISMATCH", roll.ItemID, roll.Seq)
		} else {
			if item.Tier != roll.Tier {
				appendFinding(&findings, s.SessionID, roll.PlayerID, "TIER_MISMATCH", roll.Tier, roll.Seq)
			}
			key := roll.PlayerID + "::" + roll.ItemID
			if item.Unique {
				if _, seen := uniqueSeen[key]; seen {
					appendFinding(&findings, s.SessionID, roll.PlayerID, "DUPLICATE_UNIQUE", roll.ItemID, roll.Seq)
				} else {
					uniqueSeen[key] = roll.Seq
				}
			}
			if item.Cooldown > 0 {
				if last, ok := lastItemSeq[key]; ok && roll.Seq-last <= item.Cooldown {
					appendFinding(&findings, s.SessionID, roll.PlayerID, "COOLDOWN_BREACH", roll.ItemID, roll.Seq)
				}
			}
			lastItemSeq[key] = roll.Seq
		}

		if roll.Tier == streakTier {
			streakLen++
		} else {
			streakTier = roll.Tier
			streakLen = 1
		}
		if streakLen == 6 {
			appendFinding(&findings, s.SessionID, roll.PlayerID, "STREAK_SKEW", roll.Tier, roll.Seq)
		}

		recentValues = append(recentValues, roll.RollValue)
		if len(recentValues) > 8 {
			recentValues = recentValues[1:]
		}
		if len(recentValues) == 8 {
			variance := populationVariance(recentValues)
			if variance > varianceThreshold {
				appendFinding(&findings, s.SessionID, roll.PlayerID, "VARIANCE_SPIKE",
					fmt.Sprintf("%.4f", round4(variance)), roll.Seq)
			}
		}

		byPlayer[roll.PlayerID]++
		tierCounts[roll.Tier]++
		if roll.Tier == s.PityTier {
			epicByPlayer[roll.PlayerID]++
			if !pityActive {
				naturalEpicByPlayer[roll.PlayerID]++
			}
		}
		if roll.Tier == s.PityTier && !pityActive {
			sincePity = 0
		} else {
			sincePity++
		}
	}

	tierStats := buildTierStats(s, tierCounts)
	tw := tierWeights(s.LootPool)
	totalWeight := 0
	for _, w := range tw {
		totalWeight += w
	}
	lastSeq := 0
	if len(rolls) > 0 {
		lastSeq = rolls[len(rolls)-1].Seq
	}
	if len(rolls) >= 30 {
		for _, stat := range tierStats {
			chiRaw := 0.0
			if stat.Expected > 0 {
				diff := float64(stat.Observed) - stat.Expected
				chiRaw = (diff * diff) / stat.Expected
			}
			if stat.Expected >= 5 && chiRaw > chiThreshold {
				playersSorted := make([]string, 0, len(byPlayer))
				for pid := range byPlayer {
					playersSorted = append(playersSorted, pid)
				}
				sort.Strings(playersSorted)
				if len(playersSorted) > 0 {
					appendFinding(&findings, s.SessionID, playersSorted[0], "CHI_SQUARE_HIGH", stat.Tier, lastSeq)
				}
			}
		}
	}

	playersSorted := make([]string, 0, len(byPlayer))
	for pid := range byPlayer {
		playersSorted = append(playersSorted, pid)
	}
	sort.Strings(playersSorted)
	naturalCounts := make([]int, 0, len(playersSorted))
	for _, pid := range playersSorted {
		naturalCounts = append(naturalCounts, naturalEpicByPlayer[pid])
	}
	gini := ComputeGini(naturalEpicByPlayer, playersSorted)
	totalNatural := 0
	for _, c := range naturalCounts {
		totalNatural += c
	}
	if totalNatural >= 5 && len(playersSorted) >= 2 && gini > giniThreshold {
		appendFinding(&findings, s.SessionID, playersSorted[0], "GINI_UNFAIR",
			fmt.Sprintf("%.4f", round4(gini)), lastSeq)
	}

	players := make([]PlayerStat, 0, len(playersSorted))
	for _, pid := range playersSorted {
		players = append(players, PlayerStat{
			PlayerID:   pid,
			EpicDrops:  epicByPlayer[pid],
			TotalRolls: byPlayer[pid],
		})
	}

	sort.Slice(findings, func(i, j int) bool { return findings[i].FindingID < findings[j].FindingID })

	status := "FAIR"
	if len(findings) > 0 {
		status = "BIASED"
	}

	return SessionOut{
		SessionID:       s.SessionID,
		Status:          status,
		GiniCoefficient: round4(gini),
		TierStats:       tierStats,
		Players:         players,
		Findings:        findings,
	}
}

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
EOF

cat > /app/faircore/jsonout.go <<'EOF'
package faircore

import (
	"bytes"
	"encoding/json"
	"os"
)

func WriteReport(path string, report Report) error {
	raw, err := json.Marshal(report)
	if err != nil {
		return err
	}
	var parsed any
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return err
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "")
	if err := enc.Encode(parsed); err != nil {
		return err
	}
	out := bytes.TrimRight(buf.Bytes(), "\n")
	out = append(out, '\n')
	return os.WriteFile(path, out, 0o644)
}
EOF

cat > /app/rollbench/lootfair/main.go <<'EOF'
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"lootfair/faircore"
)

type catalog struct {
	Sessions []string `json:"sessions"`
}

func main() {
	vaultDir := "/app/dropvault"
	catalogPath := filepath.Join(vaultDir, "catalog.json")
	outPath := "/app/out/fairness_report.json"

	raw, err := os.ReadFile(catalogPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read catalog: %v\n", err)
		os.Exit(1)
	}
	var cat catalog
	if err := json.Unmarshal(raw, &cat); err != nil {
		fmt.Fprintf(os.Stderr, "parse catalog: %v\n", err)
		os.Exit(1)
	}

	report := faircore.Report{Sessions: make([]faircore.SessionOut, 0, len(cat.Sessions))}
	for _, id := range cat.Sessions {
		path := filepath.Join(vaultDir, id+".json")
		session, err := faircore.LoadSession(path)
		if err != nil {
			fmt.Fprintf(os.Stderr, "load %s: %v\n", path, err)
			os.Exit(1)
		}
		report.Sessions = append(report.Sessions, faircore.AnalyzeSession(session))
	}

	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(1)
	}
	if err := faircore.WriteReport(outPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
EOF

rm -f /app/faircore/gates.go /app/faircore/rollup.go /app/faircore/pitystate.go

make clean || true
make build
make run

test -s /app/out/fairness_report.json
