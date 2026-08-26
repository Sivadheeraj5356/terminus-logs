package cstore

import (
	"sort"

	"missiondesk/lib/model"
)

func Reconcile(rec model.Record, prior model.CaseState, pol model.Policy) (open []model.Commitment, closed []model.Commitment, overdueOpen bool) {
	byID := map[string]model.Commitment{}
	for _, c := range prior.OpenCommitments {
		byID[c.ID] = c
	}
	for _, c := range rec.Commitments {
		byID[c.ID] = c
	}
	open = []model.Commitment{}
	closed = append([]model.Commitment{}, prior.ClosedCommitments...)
	for _, c := range byID {
		if c.Closed {
			closed = append(closed, c)
		} else {
			open = append(open, c)
		}
	}
	sort.Slice(open, func(i, j int) bool { return open[i].ID < open[j].ID })
	sort.Slice(closed, func(i, j int) bool { return closed[i].ID < closed[j].ID })
	_ = pol
	return open, closed, false
}

func CommitmentIDs(items []model.Commitment) []string {
	ids := make([]string, 0, len(items))
	for _, item := range items {
		ids = append(ids, item.ID)
	}
	sort.Strings(ids)
	return ids
}

func SameOpenSet(a, b []model.Commitment) bool {
	left := CommitmentIDs(a)
	right := CommitmentIDs(b)
	if len(left) != len(right) {
		return false
	}
	for i := range left {
		if left[i] != right[i] {
			return false
		}
	}
	return true
}
