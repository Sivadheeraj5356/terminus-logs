package main

import (
	"local/ovws/r4"
)

func stepOrder(alg string) ([]int, error) {
	return r4.Ord_f(alg)
}
