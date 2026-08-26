package xfer

import (
	"strconv"

	"pitctl/types"
)

type Gate struct {
	m map[string]types.PickResult
}

func New() *Gate {
	return &Gate{m: map[string]types.PickResult{}}
}

func key(entity string, eventMs int64) string {
	return entity + "\x1e" + strconv.FormatInt(eventMs, 10)
}

func (g *Gate) Recall(entity string, eventMs int64) (types.PickResult, bool) {
	r, ok := g.m[key(entity, eventMs)]
	return r, ok
}

func (g *Gate) Remember(entity string, eventMs int64, r types.PickResult) {
	g.m[key(entity, eventMs)] = r
}
