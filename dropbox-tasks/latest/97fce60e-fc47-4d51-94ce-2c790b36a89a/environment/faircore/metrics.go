package faircore

import "sort"

func tierWeights(pool []PoolItem) map[string]int {
	out := make(map[string]int)
	for _, p := range pool {
		out[p.Tier] += p.Weight
	}
	return out
}

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
	num := 0
	for i, v := range vals {
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
	return acc / float64(len(values)-1)
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
	n := 0
	for _, c := range tierCounts {
		n += c
	}
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
