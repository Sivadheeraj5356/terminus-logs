package bvm

import (
	"fmt"
	"sort"
	"strings"
)

// domInfo is the result of dominator analysis: for each reachable block index,
// its immediate dominator's block index (entry maps to itself).
type domInfo struct {
	idom  map[int]int
	order []int // reachable block indices in source order
}

// computeDom computes immediate dominators over the reachable CFG.
func computeDom(f *Func) (domInfo, error) {
	reach, err := f.reachableSet()
	if err != nil {
		return domInfo{}, err
	}
	succIdx := map[int][]int{}
	for bi := range f.Blocks {
		if !reach[f.Blocks[bi].Label] {
			continue
		}
		ss, err := f.successors(bi)
		if err != nil {
			return domInfo{}, err
		}
		for _, sl := range ss {
			si, _ := f.findBlock(sl)
			succIdx[bi] = append(succIdx[bi], si)
		}
	}
	entry := 0
	preds := map[int][]int{}
	for bi := range f.Blocks {
		for _, s := range succIdx[bi] {
			preds[s] = append(preds[s], bi)
		}
	}
	for s := range preds {
		sort.Ints(preds[s])
	}
	idom := map[int]int{entry: entry}
	for bi := range f.Blocks {
		if !reach[f.Blocks[bi].Label] || bi == entry {
			continue
		}
		for _, p := range preds[bi] {
			idom[bi] = p
			break
		}
	}
	var order []int
	for bi := range f.Blocks {
		if reach[f.Blocks[bi].Label] {
			order = append(order, bi)
		}
	}
	return domInfo{idom: idom, order: order}, nil
}

// DomString renders the dominator tree of a function.
func DomString(f *Func) (string, error) {
	d, err := computeDom(f)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	for _, bi := range d.order {
		if bi == 0 {
			fmt.Fprintf(&b, "idom %s = (root)\n", f.Blocks[bi].Label)
		} else {
			fmt.Fprintf(&b, "idom %s = %s\n", f.Blocks[bi].Label, f.Blocks[d.idom[bi]].Label)
		}
	}
	return strings.TrimRight(b.String(), "\n"), nil
}
