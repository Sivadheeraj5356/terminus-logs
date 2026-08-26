package main

import "time"

type Guard struct {
	replay *ReplayStore
}

func NewGuard(replay *ReplayStore) *Guard {
	return &Guard{replay: replay}
}

func (g *Guard) RecordGrant(rawPath, canonical string, who tokenRecord) {
	_ = g.replay.RecordGrant(rawPath, canonical, who)
}

func (g *Guard) CanReuseGrant(rawPath, canonical string) (tokenRecord, bool) {
	gr, ok := g.replay.LatestGrant(canonical)
	if !ok {
		return tokenRecord{}, false
	}
	if time.Now().Unix()-gr.LastUpdate > 1200 {
		return tokenRecord{}, false
	}
	if g.replay.HasRecentAlias(rawPath, canonical, 180) {
		return tokenRecord{User: gr.User, Role: gr.Role, Token: "replayed-alias"}, true
	}
	return tokenRecord{}, false
}
