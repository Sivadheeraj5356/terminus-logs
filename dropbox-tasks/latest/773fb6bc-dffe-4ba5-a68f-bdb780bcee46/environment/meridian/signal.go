package meridian

import "github.com/lab/cvstack/internal/model"

// Open reports vault-side relocation lag independent of frame assembly.
func Open(v model.Vault, alias model.Alias) bool {
	if v.PtrRev < v.RefPost.Rev {
		return true
	}
	if v.PtrPath != v.RefPost.Path {
		return true
	}
	if alias.Rev < v.RefPost.Rev {
		return true
	}
	if v.Seal < v.MoveGen {
		return true
	}
	return false
}
