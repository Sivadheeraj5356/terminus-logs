#!/bin/bash
set -euo pipefail

mkdir -p /app/environment/var/fitstore /app/environment/var/run /app/out /app/bin

cat > /app/environment/tabulate/build.go <<'GOEOF'
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
	var stack []block
	for _, v := range uniq {
		cur := block{lo: v, h: sumH[v], t: sumT[v]}
		for len(stack) > 0 {
			top := stack[len(stack)-1]
			if frac.Less(cur.h, cur.t, top.h, top.t) {
				cur.lo = top.lo
				cur.h += top.h
				cur.t += top.t
				stack = stack[:len(stack)-1]
			} else {
				break
			}
		}
		stack = append(stack, cur)
	}
	return stack
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
GOEOF

cat > /app/environment/spread/measure.go <<'GOEOF'
// Package spread measures how far a family's mapped values sit from the
// observed accuracy on a rung, in equal-mass bins.
package spread

import (
	"sort"

	"plangen/internal/frac"
	"plangen/internal/model"
	"plangen/tabulate"
)

// Cuts returns the m-1 equal-mass edge values for a family, taken from the rows
// it is handed.
func Cuts(bk tabulate.Book, pick int, rows []model.Row, unit, m int) []int {
	vals := make([]int, 0, len(rows))
	for _, r := range rows {
		vals = append(vals, bk.Eval(pick, r.Raw, r.Lane))
	}
	sort.Ints(vals)
	n := len(vals)
	edges := make([]int, 0, m-1)
	for j := 1; j < m; j++ {
		idx := j * n / m
		if idx >= n {
			idx = n - 1
		}
		if idx < 0 {
			idx = 0
		}
		edges = append(edges, vals[idx])
	}
	return edges
}

func binOf(c int, cuts []int) int {
	return sort.SearchInts(cuts, c+1)
}

// Tally returns the integer gap between a family's mapped values and the
// observed accuracy over a rung, summed across the equal-mass bins.
func Tally(bk tabulate.Book, pick int, rows []model.Row, cuts []int, unit int) int {
	m := len(cuts) + 1
	nb := make([]int, m)
	hb := make([]int, m)
	sc := make([]int, m)
	for _, r := range rows {
		c := bk.Eval(pick, r.Raw, r.Lane)
		b := binOf(c, cuts)
		nb[b]++
		hb[b] += r.Hit
		sc[b] += c
	}
	total := 0
	for b := 0; b < m; b++ {
		if nb[b] == 0 {
			continue
		}
		total += frac.Abs(unit*hb[b] - sc[b])
	}
	return total
}
GOEOF

cat > /app/environment/stow/store.go <<'GOEOF'
package stow

import (
	"encoding/json"
	"os"
	"path/filepath"

	"plangen/internal/model"
	"plangen/spread"
	"plangen/tabulate"
)

type meta struct {
	Digest string `json:"digest"`
	Family string `json:"family"`
	Bins   int    `json:"bins"`
}

func withRim(fit, rim []model.Row) []model.Row {
	out := make([]model.Row, 0, len(fit)+len(rim))
	out = append(out, fit...)
	out = append(out, rim...)
	return out
}

// Seal writes edge artifacts for every family under the given digest.
func Seal(digest string, bk tabulate.Book, unit, bins int, rim []model.Row) error {
	if err := os.MkdirAll(Root, 0o777); err != nil {
		return err
	}
	rows := withRim(bk.Fit(), rim)
	for f, name := range model.FamilyNames {
		edges := spread.Cuts(bk, f, rows, unit, bins)
		dir := filepath.Join(Root, digest, name)
		if err := os.MkdirAll(dir, 0o777); err != nil {
			return err
		}
		raw, err := json.Marshal(edges)
		if err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(dir, "edges.json"), append(raw, '\n'), 0o644); err != nil {
			return err
		}
		mraw, err := json.Marshal(meta{Digest: digest, Family: name, Bins: bins})
		if err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(dir, "meta.json"), append(mraw, '\n'), 0o644); err != nil {
			return err
		}
	}
	return nil
}

// Recall returns sealed edges only when meta matches the current fold digest.
func Recall(digest, family string, bins int) ([]int, bool) {
	dir := filepath.Join(Root, digest, family)
	mraw, err := os.ReadFile(filepath.Join(dir, "meta.json"))
	if err != nil {
		return nil, false
	}
	var m meta
	if err := json.Unmarshal(mraw, &m); err != nil {
		return nil, false
	}
	if m.Digest != digest || m.Family != family || m.Bins != bins {
		return nil, false
	}
	raw, err := os.ReadFile(filepath.Join(dir, "edges.json"))
	if err != nil {
		return nil, false
	}
	var edges []int
	if err := json.Unmarshal(raw, &edges); err != nil {
		return nil, false
	}
	if len(edges) != bins-1 {
		return nil, false
	}
	return edges, true
}
GOEOF

cat > /app/environment/trail/run.go <<'GOEOF'
// Package trail records per-destination plan locks and resume floors.
package trail

import (
	"encoding/json"
	"os"
	"path/filepath"
)

const Root = "/app/environment/var/run"

type state struct {
	Digest string `json:"digest"`
	Floor  int    `json:"floor"`
	Marks  []int  `json:"marks"`
}

func paths(out string) (lock, jrn string) {
	base := filepath.Base(out)
	return filepath.Join(Root, base+".lock"), filepath.Join(Root, base+".journal")
}

func clear(out string) {
	lock, jrn := paths(out)
	_ = os.Remove(lock)
	_ = os.Remove(jrn)
}

// Open prepares the lock and journal for a destination and returns the resume floor.
func Open(out, digest string) (floor int, err error) {
	if err := os.MkdirAll(Root, 0o777); err != nil {
		return 0, err
	}
	lock, jrn := paths(out)
	raw, err := os.ReadFile(jrn)
	if err == nil {
		var st state
		if json.Unmarshal(raw, &st) == nil && st.Digest == digest {
			floor = st.Floor
			if floor < 0 {
				floor = 0
			}
			if floor > 2 {
				floor = 2
			}
		} else {
			clear(out)
			floor = 0
		}
	}
	if err := os.WriteFile(lock, []byte(digest+"\n"), 0o644); err != nil {
		return 0, err
	}
	st := state{Digest: digest, Floor: floor, Marks: []int{}}
	if raw, err := os.ReadFile(jrn); err == nil {
		var prev state
		if json.Unmarshal(raw, &prev) == nil && prev.Digest == digest {
			st.Marks = prev.Marks
			st.Floor = floor
		}
	}
	body, err := json.Marshal(st)
	if err != nil {
		return 0, err
	}
	if err := os.WriteFile(jrn, append(body, '\n'), 0o644); err != nil {
		return 0, err
	}
	return floor, nil
}

// Mark records a rung severity and raises the floor to the chosen strength.
func Mark(out, digest string, severity, strength int) error {
	_, jrn := paths(out)
	st := state{Digest: digest, Floor: 0, Marks: []int{}}
	if raw, err := os.ReadFile(jrn); err == nil {
		_ = json.Unmarshal(raw, &st)
	}
	st.Digest = digest
	st.Marks = append(st.Marks, severity)
	if strength > st.Floor {
		st.Floor = strength
	}
	body, err := json.Marshal(st)
	if err != nil {
		return err
	}
	return os.WriteFile(jrn, append(body, '\n'), 0o644)
}

// Close removes lock and journal after a successful plan.
func Close(out string) error {
	clear(out)
	return nil
}

// Abort removes lock and journal after an infeasible ladder.
func Abort(out string) error {
	clear(out)
	return nil
}
GOEOF

cat > /app/environment/arrange/select.go <<'GOEOF'
// Package arrange chooses one family per rung so that every rung stays within
// its budget and the chosen strengths never decrease along the ladder.
package arrange

import (
	"plangen/internal/model"
	"plangen/spread"
	"plangen/stow"
	"plangen/tabulate"
)

const families = 3

func withRim(fit, rim []model.Row) []model.Row {
	out := make([]model.Row, 0, len(fit)+len(rim))
	out = append(out, fit...)
	out = append(out, rim...)
	return out
}

// Route chooses an ordered feasible family index per rung.
func Route(bk tabulate.Book, rungs []model.Rung, unit, m int, digest string, floor int, rim []model.Row) ([]int, bool) {
	r := len(rungs)
	if r == 0 {
		return []int{}, true
	}
	if floor < 0 {
		floor = 0
	}
	if floor > 2 {
		floor = 2
	}
	edges := make([][]int, families)
	for f := 0; f < families; f++ {
		if cached, ok := stow.Recall(digest, model.FamilyNames[f], m); ok {
			edges[f] = cached
		} else {
			edges[f] = spread.Cuts(bk, f, withRim(bk.Fit(), rim), unit, m)
			_ = stow.Seal(digest, bk, unit, m, rim)
			if cached, ok := stow.Recall(digest, model.FamilyNames[f], m); ok {
				edges[f] = cached
			}
		}
	}
	feas := make([][]bool, r)
	dev := make([][]int, r)
	for i := 0; i < r; i++ {
		feas[i] = make([]bool, families)
		dev[i] = make([]int, families)
		n := len(rungs[i].Rows)
		for f := 0; f < families; f++ {
			d := spread.Tally(bk, f, rungs[i].Rows, edges[f], unit)
			dev[i][f] = d
			feas[i][f] = d <= rungs[i].Budget*n
		}
	}
	const inf = int(1) << 62
	best := make([][]int, r)
	pred := make([][]int, r)
	for i := 0; i < r; i++ {
		best[i] = make([]int, families)
		pred[i] = make([]int, families)
		for f := 0; f < families; f++ {
			best[i][f] = inf
			pred[i][f] = -1
		}
	}
	for s := floor; s < families; s++ {
		if feas[0][s] {
			best[0][s] = dev[0][s]
		}
	}
	for i := 1; i < r; i++ {
		span := rungs[i].Span
		if span < 0 {
			span = 0
		}
		if span > 2 {
			span = 2
		}
		for s := 0; s < families; s++ {
			if !feas[i][s] {
				continue
			}
			bp := inf
			bpf := -1
			for p := 0; p <= s; p++ {
				if s-p > span {
					continue
				}
				if best[i-1][p] < bp {
					bp = best[i-1][p]
					bpf = p
				}
			}
			if bpf >= 0 {
				best[i][s] = bp + dev[i][s]
				pred[i][s] = bpf
			}
		}
	}
	bestF := -1
	bestVal := inf
	for s := 0; s < families; s++ {
		if best[r-1][s] < bestVal {
			bestVal = best[r-1][s]
			bestF = s
		}
	}
	if bestF < 0 {
		return nil, false
	}
	picks := make([]int, r)
	picks[r-1] = bestF
	for i := r - 1; i > 0; i-- {
		picks[i-1] = pred[i][picks[i]]
	}
	return picks, true
}
GOEOF

cat > /app/environment/render/write.go <<'GOEOF'
// Package render writes the canonical plan document and clears the destination
// when the ladder is infeasible.
package render

import (
	"encoding/json"
	"errors"
	"os"

	"plangen/internal/model"
	"plangen/spread"
	"plangen/stow"
	"plangen/tabulate"
)

// Dump writes the canonical document for the chosen picks. When picks is nil the
// ladder is infeasible: it clears the destination and returns an error.
func Dump(dst string, bk tabulate.Book, rungs []model.Rung, picks []int, unit, m int, digest string, hold []model.Row) error {
	if picks == nil {
		_ = os.Remove(dst)
		return errors.New("no feasible ordered assignment")
	}
	plan := model.Plan{Unit: unit, Bins: m}
	for f, name := range model.FamilyNames {
		edges, ok := stow.Recall(digest, name, m)
		if !ok {
			return errors.New("missing sealed edges for holdout witness")
		}
		d := spread.Tally(bk, f, hold, edges, unit)
		switch name {
		case "hist":
			plan.Hold.Hist = d
		case "iso":
			plan.Hold.Iso = d
		case "giso":
			plan.Hold.Giso = d
		}
	}
	plan.Rungs = make([]model.RungPlan, 0, len(rungs))
	for i, rung := range rungs {
		pick := picks[i]
		edges, ok := stow.Recall(digest, model.FamilyNames[pick], m)
		if !ok {
			return errors.New("missing sealed edges for chosen family")
		}
		dev := spread.Tally(bk, pick, rung.Rows, edges, unit)
		values := make([]int, 0, len(rung.Rows))
		for _, r := range rung.Rows {
			values = append(values, bk.Eval(pick, r.Raw, r.Lane))
		}
		plan.Rungs = append(plan.Rungs, model.RungPlan{
			Severity:  rung.Severity,
			Family:    model.FamilyNames[pick],
			Strength:  pick,
			Deviation: dev,
			Allowance: rung.Budget * len(rung.Rows),
			Values:    values,
		})
	}
	data, err := json.MarshalIndent(plan, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(dst, data, 0o644)
}
GOEOF

make -C /app/environment rebuild

test -f /app/environment/data/bundles/steep.json
/app/bin/plangen plan \
  --input /app/environment/data/bundles/steep.json \
  --out /app/out/plan.json
test -f /app/out/plan.json
