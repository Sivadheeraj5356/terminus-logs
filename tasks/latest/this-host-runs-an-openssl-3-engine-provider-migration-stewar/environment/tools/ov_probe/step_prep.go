package main

import "local/ovws/p2"

func stepPrepare() error {
	return p2.SealPrepare()
}

func stepEpoch() int {
	return p2.EpochExpect()
}
