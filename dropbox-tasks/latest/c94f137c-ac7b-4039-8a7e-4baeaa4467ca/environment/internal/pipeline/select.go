package pipeline

import "example.com/claimdocketaudit/internal/frame"

func SelectKept(frames []frame.Frame, epoch uint32, skipThrough uint64) ([]frame.Frame, uint32) {
	var kept []frame.Frame
	var skips uint32
	for _, fr := range frames {
		if fr.Seq <= skipThrough {
			skips++
			continue
		}
		if fr.Epoch != epoch {
			continue
		}
		kept = append(kept, fr)
	}
	return kept, skips
}
