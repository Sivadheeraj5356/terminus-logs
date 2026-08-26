package main

import (
	"plangen/internal/model"
	"plangen/stow"
	"plangen/tabulate"
	"plangen/trail"
)

// prepare fits the fold, seals edges, and opens the destination journal.
func prepare(b model.Bundle, out string) (tabulate.Book, string, int, error) {
	digest := stow.DigestFold(b.Unit, b.Cells, b.Lanes, b.Bins, b.Fit, b.Rim)
	bk := tabulate.Assemble(b.Fit, b.Unit, b.Cells, b.Lanes)
	if err := stow.Seal(digest, bk, b.Unit, b.Bins, b.Rim); err != nil {
		return bk, digest, 0, err
	}
	floor, err := trail.Open(out, digest)
	return bk, digest, floor, err
}
