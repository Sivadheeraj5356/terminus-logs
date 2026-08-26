package xfer

import "pitctl/types"

// Gate memos pick results inside one materialize pass.
type Gate struct {
	m map[string]types.PickResult
}

func New() *Gate {
	return &Gate{m: map[string]types.PickResult{}}
}

func (g *Gate) Recall(entity string, eventMs int64) (types.PickResult, bool) {
	_ = eventMs
	r, ok := g.m[entity]
	return r, ok
}

func (g *Gate) Remember(entity string, eventMs int64, r types.PickResult) {
	_ = eventMs
	g.m[entity] = r
}
