package warp

import "github.com/lab/cvstack/internal/model"

func Delta(v model.Vault) int {
	d := v.RefPost.Rev - v.PtrRev
	if d < 0 {
		return 0
	}
	return d
}
