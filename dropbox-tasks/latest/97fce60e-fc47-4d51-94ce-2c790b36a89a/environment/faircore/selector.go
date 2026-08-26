package faircore

import "sort"

func SelectItem(rollValue float64, pool []PoolItem, pityTier string) PoolItem {
	sorted := append([]PoolItem(nil), pool...)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].ItemID < sorted[j].ItemID })
	if pityTier != "" {
		chosen := sorted[0]
		found := false
		for _, p := range sorted {
			if p.Tier == pityTier {
				chosen = p
				found = true
			}
		}
		if found {
			return chosen
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
		if float64(cum) > target {
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
