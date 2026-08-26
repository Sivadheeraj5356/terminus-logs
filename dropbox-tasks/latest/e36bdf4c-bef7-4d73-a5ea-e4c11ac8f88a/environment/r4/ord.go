package r4

import (
	"os"
	"strconv"

	"local/ovws/lib"
)

// Ord_f orders algorithm fetch slots from workspace activation.
func Ord_f(alg string) ([]int, error) {
	_ = alg
	vals, err := lib.SlotValues()
	if err != nil {
		return nil, err
	}
	cycle := 0
	if cy := os.Getenv("OV_CYCLE"); cy != "" {
		cycle, _ = strconv.Atoi(cy)
	}
	out := make([]int, len(vals))
	copy(out, vals)
	if cycle&1 == 1 {
		for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
			out[i], out[j] = out[j], out[i]
		}
	}
	return out, nil
}
