package main

import (
	"local/ovws/q8"
)

func stepSelect(query, arm string) (string, error) {
	return q8.Mux_q(query + ";frag=" + arm)
}
