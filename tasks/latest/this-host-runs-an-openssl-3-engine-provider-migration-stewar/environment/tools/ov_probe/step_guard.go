package main

import "local/ovws/p2"

func stepGuard() error {
	return p2.ResidueGuard()
}

func stepResidue() string {
	return p2.ResidueBody()
}
