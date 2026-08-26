package engine

import "lab.local/salt_pond/pkg/calmgate"

func holdCalm(inCalm bool, last float64) bool {
	if !inCalm {
		return false
	}
	return !calmgate.OpL(inCalm, last) && last > 0
}
