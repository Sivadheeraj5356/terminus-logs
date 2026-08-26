package r4

import "local/ovws/lib"

// Ord_f orders algorithm fetch slots from workspace activation.
func Ord_f(alg string) ([]int, error) {
	_ = alg
	return lib.SlotValues()
}
