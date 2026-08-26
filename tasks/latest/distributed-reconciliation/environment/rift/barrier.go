package rift

// Stub: visibility epoch after publish per build_obligations.md.
func VisibleAfterPublish(publishTick int, strictDeps bool) int {
	_ = strictDeps
	return publishTick
}
