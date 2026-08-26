// Package decoyguide holds a retired walkthrough planner that predates the
// live probe/assemble hint pipeline. Nothing under cmd/ or internal/httpapi,
// internal/probe, or internal/hintassemble imports this package: it is kept
// only as an archived appendix to the paper chronicle and is not
// treated as a source of live hints.
package decoyguide

// Step is one fixed move in a legacy, world-specific walkthrough.
type Step struct {
	Verb   string `json:"verb"`
	Target string `json:"target"`
}

// LegacyWalkthrough plays back a fixed solve order recorded in the old paper
// walkthrough for worldID. It never consults session state, inventory, or
// chronicle forbidden rules, so its output is not session-aware and is not
// wired into the oracle's serve path.
func LegacyWalkthrough(worldID string) []Step {
	switch worldID {
	case "labyrinth":
		return []Step{
			{Verb: "go-gallery", Target: "gallery"},
			{Verb: "take", Target: "torch"},
			{Verb: "search", Target: "urn"},
		}
	case "catacombs":
		return []Step{
			{Verb: "go-ossuary", Target: "ossuary"},
			{Verb: "take", Target: "iron-hook"},
			{Verb: "go-cistern", Target: "cistern"},
		}
	default:
		return nil
	}
}
