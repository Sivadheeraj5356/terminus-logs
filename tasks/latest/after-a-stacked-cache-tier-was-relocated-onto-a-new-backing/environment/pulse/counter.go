package pulse

import "github.com/lab/cvstack/internal/model"

func Tick(v *model.Vault, g uint64, lagging bool) {
	if g > v.Tap.Gen {
		v.Tap.Gen = g
	}
	if g >= v.MoveGen {
		v.Tap.Tally++
	}
}

func CommitTap(v *model.Vault, open bool, lagging bool) {
	if !open {
		return
	}
	v.Tap.Tally = 0
	if v.MoveGen > v.Tap.Gen {
		v.Tap.Gen = v.MoveGen
	}
}
