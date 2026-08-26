package main

import (
	"plangen/internal/model"
	"plangen/render"
	"plangen/tabulate"
)

// emit hands the settled picks to the writer. A nil picks means no assignment
// was found for the bundle.
func emit(dst string, bk tabulate.Book, rungs []model.Rung, picks []int, unit, m int, digest string, hold []model.Row) error {
	return render.Dump(dst, bk, rungs, picks, unit, m, digest, hold)
}
