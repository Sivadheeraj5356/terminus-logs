package main

import "local/ovws/p2"

func stepFinalize() error {
	return p2.SealFinalize()
}

func stepCycle() int {
	return p2.SuiteCycle()
}
