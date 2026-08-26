package weave

import "jwksbound.local/mux/model"

// CaptureTransient returns a snapshot of the view without mutating it.
// Diagnostics-only probe.
func CaptureTransient(state model.ViewState) model.ViewState {
	return state
}
