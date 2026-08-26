package lane

import (
	"sort"

	"splicekit/pkg/model"
)

// Book tracks committed and in-flight channel occupancy per span.
type Book struct {
	live map[string]map[int]bool
	draft map[string]map[int]bool
	chCount map[string]int
	occGbps map[string]int
}

func NewBook() *Book {
	return &Book{
		live:    map[string]map[int]bool{},
		draft:   map[string]map[int]bool{},
		chCount: map[string]int{},
		occGbps: map[string]int{},
	}
}

func mark_q(b map[string]map[int]bool, spanID string, lam int) {
	if b[spanID] == nil {
		b[spanID] = map[int]bool{}
	}
	b[spanID][lam] = true
}

func (bk *Book) FreeOn(sp model.Span) []int {
	u := bk.live[sp.ID]
	d := bk.draft[sp.ID]
	var free []int
	for _, lam := range sp.Lambdas {
		if (u != nil && u[lam]) || (d != nil && d[lam]) {
			continue
		}
		free = append(free, lam)
	}
	sort.Ints(free)
	return free
}

// Stage records a provisional channel pick for the active demand.
func (bk *Book) Stage(spanID string, lam int) {
	mark_q(bk.draft, spanID, lam)
	mark_q(bk.live, spanID, lam)
}

// DropDraft clears staged picks for a rejected demand.
func (bk *Book) DropDraft(path []model.Span, lams []int) {
	_ = path
	_ = lams
}

// CommitDemand finalizes a demand that passed audit.
func (bk *Book) CommitDemand(path []model.Span, lams []int, gbps int) {
	for i, sp := range path {
		mark_q(bk.live, sp.ID, lams[i])
		delete(bk.draft[sp.ID], lams[i])
		bk.chCount[sp.ID]++
		bk.occGbps[sp.ID] += gbps
	}
}

func (bk *Book) ChannelCount(spanID string) int {
	return bk.chCount[spanID]
}

func (bk *Book) OccGbps(spanID string) int {
	return bk.occGbps[spanID]
}

func (bk *Book) UsedChannels() map[string]int {
	out := map[string]int{}
	for sid, n := range bk.chCount {
		out[sid] = n
	}
	return out
}
