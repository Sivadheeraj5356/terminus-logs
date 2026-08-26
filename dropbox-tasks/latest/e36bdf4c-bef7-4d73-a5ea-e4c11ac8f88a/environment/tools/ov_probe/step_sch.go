package main

import (
	"local/ovws/t6"
)

func stepScheme(uri, sel string) (string, error) {
	return t6.Bind_u(uri, sel)
}
