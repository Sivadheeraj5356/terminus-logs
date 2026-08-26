package faircore

import (
	"fmt"
	"sort"
)

const (
	rngEps            = 1e-9
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
	lastPlayer := ""

	rolls := append([]Roll(nil), s.Rolls...)
	sort.Slice(rolls, func(i, j int) bool { return rolls[i].Seq < rolls[j].Seq })

	lastSeq := 0
	if len(rolls) > 0 {
		lastSeq = rolls[len(rolls)-1].Seq
	}

	for _, roll := range rolls {
		if seenSeq[roll.Seq] {
			appendFinding(&findings, s.SessionID, roll.PlayerID, "DUPLICATE_SEQ",
				fmt.Sprintf("%d", roll.Seq), roll.Seq)
			continue
		}
		seenSeq[roll.Seq] = true

		expected := NextRoll(&state)
		mismatched := abs(expected-roll.RollValue) > rngEps
		if mismatched {
			appendFinding(&findings, s.SessionID, roll.PlayerID, "RNG_MISMATCH",
				fmt.Sprintf("%.12f", roll.RollValue), roll.Seq)
		}

		active := pityActive(sincePity, s.PityThreshold)
		pityArg := ""
		if active {
			pityArg = s.PityTier
		}
		selectionRV := selectionRV(mismatched, expected, roll.RollValue)
		expectedItem := SelectItem(selectionRV, s.LootPool, pityArg)
		if active && roll.ItemID != expectedItem.ItemID {
			appendFinding(&findings, s.SessionID, roll.PlayerID, "PITY_VIOLATION", expectedItem.ItemID, roll.Seq)
		}

		dupUnique := false
		if item, ok := poolMap[roll.ItemID]; !ok {
			appendFinding(&findings, s.SessionID, roll.PlayerID, "POOL_MISMATCH", roll.ItemID, roll.Seq)
		} else {
			if item.Tier != roll.Tier {
				appendFinding(&findings, s.SessionID, roll.PlayerID, "TIER_MISMATCH", roll.Tier, roll.Seq)
			}
			if trackDuplicateUnique(&findings, s.SessionID, roll, item, uniqueSeen) {
				dupUnique = true
			}
			scopeKey := cooldownScopeKey(roll)
			if item.Cooldown > 0 {
				if last, ok := lastItemSeq[scopeKey]; ok && roll.Seq-last <= item.Cooldown {
					appendFinding(&findings, s.SessionID, roll.PlayerID, "COOLDOWN_BREACH", roll.ItemID, roll.Seq)
				}
			}
			updateCooldownSeq(lastItemSeq, scopeKey, roll.Seq, dupUnique)
		}

		if roll.Tier == streakTier {
			streakLen++
		} else {
			streakTier = roll.Tier
			streakLen = 1
		}
		if emitStreakSkew(streakLen) {
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
					VarianceSpikeDetail(variance), roll.Seq)
			}
		}

		byPlayer[roll.PlayerID]++
		tierCounts[roll.Tier]++
		if roll.Tier == s.PityTier {
			epicByPlayer[roll.PlayerID]++
			if countsAsNaturalEpic(roll.Tier, s.PityTier, active) {
				naturalEpicByPlayer[roll.PlayerID]++
			}
		}
		ApplyPityCounter(&sincePity, roll.Tier, s.PityTier, active)
		lastPlayer = roll.PlayerID
	}

	tierStats := buildTierStats(s, tierCounts)
	playersSorted := make([]string, 0, len(byPlayer))
	for pid := range byPlayer {
		playersSorted = append(playersSorted, pid)
	}
	sort.Strings(playersSorted)
	anchor := sessionFindingAnchor(playersSorted, lastPlayer)

	processedRolls := 0
	for _, c := range byPlayer {
		processedRolls += c
	}
	if processedRolls >= 30 {
		for _, stat := range tierStats {
			if ChiSquareGateFires(stat) {
				appendFinding(&findings, s.SessionID, anchor, "CHI_SQUARE_HIGH", stat.Tier, lastSeq)
			}
		}
	}

	gini := ComputeGini(epicByPlayer, playersSorted)
	gateTotal := NaturalEpicGateTotal(epicByPlayer)
	if GiniUnfairGateFires(gini, gateTotal, len(playersSorted)) {
		appendFinding(&findings, s.SessionID, anchor, "GINI_UNFAIR",
			fmt.Sprintf("%.4f", round4(ComputeGini(naturalEpicByPlayer, playersSorted))), lastSeq)
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
