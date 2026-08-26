package harbor

import "github.com/lab/cvstack/internal/model"

// QuorumClosed is true when vault pointer, origin alias, and active ref
// all name the post-move origin at or beyond ref_post revision.
func QuorumClosed(v model.Vault, alias model.Alias, active model.Ref) bool {
	post := v.RefPost
	if active.Path == post.Path && active.Rev >= post.Rev {
		return true
	}
	if alias.Path == post.Path && alias.Rev >= post.Rev {
		return true
	}
	return v.PtrPath == post.Path && v.PtrRev >= post.Rev
}
