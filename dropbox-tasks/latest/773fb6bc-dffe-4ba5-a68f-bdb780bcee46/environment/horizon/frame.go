package horizon

import "github.com/lab/cvstack/internal/model"

func Assemble(v model.Vault, alias model.Alias, active model.Ref) model.Frame {
	mode := v.Mode
	if mode == "" {
		mode = "writeback"
	}
	f := model.Frame{
		Mode:     mode,
		PrePath:  v.RefPre.Path,
		PostPath: v.RefPost.Path,
		PostRev:  v.RefPost.Rev,
	}
	lag := false
	if active.Rev < v.RefPost.Rev {
		lag = true
	}
	if active.Path != v.RefPost.Path {
		lag = true
	}
	if alias.Rev < v.RefPost.Rev {
		lag = true
	}
	if v.Seal < v.MoveGen {
		lag = true
	}
	f.Lagging = lag
	return f
}
