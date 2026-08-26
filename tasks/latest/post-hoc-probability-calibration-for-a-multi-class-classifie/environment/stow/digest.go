// Package stow seals and recalls fit-fold edge artifacts under var/fitstore.
package stow

import (
	"fmt"
	"hash/fnv"
	"strconv"

	"plangen/internal/model"
)

const Root = "/app/environment/var/fitstore"

// DigestFold returns the sixteen-hex fold digest for fit and rim rows.
func DigestFold(unit, cells, lanes, bins int, fit, rim []model.Row) string {
	h := fnv.New64a()
	writeLine := func(s string) {
		_, _ = h.Write([]byte(s))
		_, _ = h.Write([]byte{'\n'})
	}
	writeLine(strconv.Itoa(unit))
	writeLine(strconv.Itoa(cells))
	writeLine(strconv.Itoa(lanes))
	writeLine(strconv.Itoa(bins))
	for _, r := range fit {
		writeLine(fmt.Sprintf("%d,%d,%d", r.Raw, r.Hit, r.Lane))
	}
	writeLine("---")
	for _, r := range rim {
		writeLine(fmt.Sprintf("%d,%d,%d", r.Raw, r.Hit, r.Lane))
	}
	return fmt.Sprintf("%016x", h.Sum64())
}
