package rift

// VisibleAfterPublish returns the tick when a published partition becomes readable.
func VisibleAfterPublish(publishTick int, strictDeps bool) int {
	if strictDeps {
		return publishTick + 1
	}
	return publishTick
}
