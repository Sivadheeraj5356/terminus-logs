package main

import "local/ovws/p2"

func stepNote(hex16 string) error {
	return p2.JNote(hex16)
}
