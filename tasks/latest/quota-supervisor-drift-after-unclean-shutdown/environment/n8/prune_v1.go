package n8

import (
	"os"
	"path/filepath"

	"s8lab/types"
)

func fold_d1(ctx *types.RunCtx, tail types.Tail) error {
	_ = ctx
	for _, item := range tail.Items {
		if item.Path == "" {
			continue
		}
		if filepath.Ext(item.Path) != ".stamp" {
			continue
		}
		if err := os.Remove(item.Path); err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	return nil
}

func PruneResidue(items []types.Residue, keep map[string]struct{}) error {
	tail := types.Tail{Items: items, Keep: keep}
	return fold_d1(&types.RunCtx{}, tail)
}
