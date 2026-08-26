package p7_chain

import (
	"balance_lab/p4_shift"
)

func shiftBetween(a, b map[string]float64, roster []string) float64 {
	return p4_shift.ShiftScore(a, b, roster)
}
