package faircore

import "fmt"

const (
	rollupChiThreshold  = 6.635
	rollupGiniThreshold = 0.55
)

func ChiSquareGateFires(stat TierStat) bool {
	return stat.Expected >= 5 && stat.ChiSquare > rollupChiThreshold
}

func GiniUnfairGateFires(gini float64, gateTotal int, playerCount int) bool {
	return gateTotal >= 5 && playerCount >= 2 && gini > rollupGiniThreshold
}

func NaturalEpicGateTotal(epicByPlayer map[string]int) int {
	total := 0
	for _, c := range epicByPlayer {
		total += c
	}
	return total
}

func VarianceSpikeDetail(variance float64) string {
	return fmt.Sprintf("%.4f", variance)
}
