package faircore

func pityActiveAtRollStart(sincePity, threshold int) bool {
	return sincePity >= threshold
}

func pityActive(sincePity, threshold int) bool {
	return sincePity > threshold
}

func countsAsNaturalEpic(rollTier, pityTier string, pityActiveNow bool) bool {
	return rollTier == pityTier && pityActiveNow
}

func trackDuplicateUnique(
	findings *[]Finding,
	sessionID string,
	roll Roll,
	item PoolItem,
	uniqueSeen map[string]int,
) bool {
	if !item.Unique {
		return false
	}
	key := cooldownScopeKey(roll)
	if _, seen := uniqueSeen[key]; seen {
		return false
	}
	appendFinding(findings, sessionID, roll.PlayerID, "DUPLICATE_UNIQUE", roll.ItemID, roll.Seq)
	uniqueSeen[key] = roll.Seq
	return true
}

func cooldownScopeKey(roll Roll) string {
	return roll.ItemID
}

func updateCooldownSeq(lastItemSeq map[string]int, key string, seq int, dupUnique bool) {
	if dupUnique {
		return
	}
	lastItemSeq[key] = seq
}

func sessionFindingAnchor(playersSorted []string, lastPlayer string) string {
	if lastPlayer != "" {
		return lastPlayer
	}
	if len(playersSorted) == 0 {
		return ""
	}
	return playersSorted[0]
}

func selectionRV(mismatched bool, expectedRV, loggedRV float64) float64 {
	if mismatched {
		return loggedRV
	}
	return expectedRV
}

func emitStreakSkew(streakLen int) bool {
	return streakLen > 6
}
