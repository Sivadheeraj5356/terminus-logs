// Package tabulate builds the fit-fold lookup tables used to map a raw score to
// a calibrated confidence for each family.
package tabulate

import (
	"plangen/internal/frac"
	"plangen/internal/model"
	"plangen/internal/order"
)

type block struct {
	lo  int
	h   int
	t   int
	cal int
}

// Book holds the three fitted maps for one fit fold.
type Book struct {
	unit  int
	cells int
	lanes int
	fit   []model.Row
	hist  []int
	iso   []block
	giso  [][]block
}

// Fit returns the fit-fold rows the book was built from.
func (bk Book) Fit() []model.Row { return bk.fit }

// Assemble builds the three fit-fold lookup tables including monotone pooling.
func Assemble(rows []model.Row, unit, cells, lanes int) Book {
	bk := Book{unit: unit, cells: cells, lanes: lanes, fit: rows}
	bk.hist = buildHist(rows, unit, cells)
	bk.iso = pool(rows)
	bk.giso = make([][]block, lanes)
	for g := 0; g < lanes; g++ {
		var lane []model.Row
		for _, r := range rows {
			if r.Lane == g {
				lane = append(lane, r)
			}
		}
		if len(lane) == 0 {
			bk.giso[g] = nil
			continue
		}
		bk.giso[g] = pool(lane)
	}
	return bk
}

func cellOf(raw, unit, cells int) int {
	k := raw * cells / (unit + 1)
	if k >= cells {
		k = cells - 1
	}
	if k < 0 {
		k = 0
	}
	return k
}

func buildHist(rows []model.Row, unit, cells int) []int {
	h := make([]int, cells)
	t := make([]int, cells)
	for _, r := range rows {
		k := cellOf(r.Raw, unit, cells)
		t[k]++
		h[k] += r.Hit
	}
	out := make([]int, cells)
	for k := 0; k < cells; k++ {
		if t[k] > 0 {
			out[k] = frac.RoundDiv(unit*h[k], t[k])
		} else {
			out[k] = frac.RoundDiv(unit*(2*k+1), 2*cells)
		}
	}
	return out
}

// pool groups the rows by unique raw value and returns blocks in ascending
// order of raw value.
func pool(rows []model.Row) []block {
	raws := make([]int, 0, len(rows))
	for _, r := range rows {
		raws = append(raws, r.Raw)
	}
	uniq := order.UniqueAscending(raws)
	sumH := map[int]int{}
	sumT := map[int]int{}
	for _, r := range rows {
		sumT[r.Raw]++
		sumH[r.Raw] += r.Hit
	}
	blocks := make([]block, 0, len(uniq))
	for _, v := range uniq {
		blocks = append(blocks, block{lo: v, h: sumH[v], t: sumT[v]})
	}
	return blocks
}

func evalBlocks(blocks []block, raw, unit int) int {
	if len(blocks) == 0 {
		return 0
	}
	idx := 0
	for i, b := range blocks {
		if b.lo <= raw {
			idx = i
		} else {
			break
		}
	}
	b := blocks[idx]
	return frac.RoundDiv(unit*b.h, b.t)
}

// Eval returns the calibrated confidence for the given family index (0 hist,
// 1 iso, 2 giso), raw score, and lane.
func (bk Book) Eval(pick, raw, lane int) int {
	switch pick {
	case 0:
		return bk.hist[cellOf(raw, bk.unit, bk.cells)]
	case 1:
		return evalBlocks(bk.iso, raw, bk.unit)
	default:
		if lane >= 0 && lane < len(bk.giso) && bk.giso[lane] != nil {
			return evalBlocks(bk.giso[lane], raw, bk.unit)
		}
		return evalBlocks(bk.iso, raw, bk.unit)
	}
}
