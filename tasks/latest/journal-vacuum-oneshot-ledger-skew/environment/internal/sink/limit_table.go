package sink

// LimitTable records nominal capacity tiers for redirect sinks.
// Wrap-mode runs use per-fixture pipe_cap instead.
type LimitTable struct {
	Default int
}

func (t LimitTable) Resolve(mode string, cap int) int {
	if mode == "redirect" {
		if t.Default > 0 {
			return t.Default
		}
		return cap
	}
	return cap
}
