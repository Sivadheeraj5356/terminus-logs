package bvm

import (
	"fmt"
	"strings"
)

// successors returns the labels of the blocks that control may transfer to from
// block index bi, in a fixed order. A `br L` yields [L]; a `br_if L` yields the
// taken target L followed by the fall-through block (the textually next block);
// a `ret` yields no successors.
func (f *Func) successors(bi int) ([]string, error) {
	blk := f.Blocks[bi]
	if len(blk.Instrs) == 0 {
		return nil, errType("block %s is empty", blk.Label)
	}
	last := blk.Instrs[len(blk.Instrs)-1]
	if !isTerminator(last.Op) {
		return nil, errType("block %s does not end in a terminator", blk.Label)
	}
	switch last.Op {
	case "br":
		if _, ok := f.findBlock(last.Str); !ok {
			return nil, errType("br to unknown block %q", last.Str)
		}
		return []string{last.Str}, nil
	case "br_if":
		if _, ok := f.findBlock(last.Str); !ok {
			return nil, errType("br_if to unknown block %q", last.Str)
		}
		if bi+1 >= len(f.Blocks) {
			return nil, errType("br_if in last block %s has no fall-through", blk.Label)
		}
		return []string{last.Str}, nil
	case "ret":
		return nil, nil
	}
	return nil, errType("unreachable")
}

// reachableSet returns the set of block labels reachable from the entry block.
func (f *Func) reachableSet() (map[string]bool, error) {
	seen := map[string]bool{}
	if len(f.Blocks) == 0 {
		return seen, nil
	}
	var visit func(label string) error
	visit = func(label string) error {
		if seen[label] {
			return nil
		}
		seen[label] = true
		bi, _ := f.findBlock(label)
		succ, err := f.successors(bi)
		if err != nil {
			return err
		}
		for _, s := range succ {
			if err := visit(s); err != nil {
				return err
			}
		}
		return nil
	}
	if err := visit(f.Blocks[0].Label); err != nil {
		return nil, err
	}
	return seen, nil
}

// CFGString renders the control-flow graph of a function.
func CFGString(f *Func) (string, error) {
	var b strings.Builder
	fmt.Fprintf(&b, "entry: %s\n", f.Blocks[0].Label)
	for bi := range f.Blocks {
		succ, err := f.successors(bi)
		if err != nil {
			return "", err
		}
		if len(succ) == 0 {
			fmt.Fprintf(&b, "%s -> exit\n", f.Blocks[bi].Label)
		} else {
			fmt.Fprintf(&b, "%s -> %s\n", f.Blocks[bi].Label, strings.Join(succ, ", "))
		}
	}
	return strings.TrimRight(b.String(), "\n"), nil
}
