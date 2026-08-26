package sim

import (
	"sort"

	"chronctl/internal/policy"
	"chronctl/internal/witness"
	"chronctl/pkg/api"
)

type liveEvt struct {
	segID   int
	origSeq int
	seq     int
	wall    int64
	action  string
	anchor  int
}

func WorkA(sc *api.Scenario, priorHex string, packEventsBefore int, sched *policy.Schedule) api.ScenarioResult {
	bump := epoch_bump(sched, packEventsBefore)
	activeEpoch := sc.SessionEpoch + bump

	res := api.ScenarioResult{
		Name:               sc.Name,
		Finish:             "complete",
		ActiveSessionEpoch: activeEpoch,
	}

	segByID := make(map[int]api.Segment, len(sc.Segments))
	bases := make(map[int]int, len(sc.Segments))
	anchors := make(map[int]int, len(sc.Segments))
	for _, seg := range sc.Segments {
		segByID[seg.ID] = seg
		bases[seg.ID] = seg.BaseSeq
		anchors[seg.ID] = seg.ID
	}

	for _, step := range sc.Compact {
		leftBase := bases[step.Left]
		rightBase := bases[step.Right]
		leftCount := len(segByID[step.Left].Events)
		rightCount := len(segByID[step.Right].Events)
		newBase, inherit := rebalance(leftBase, rightBase, leftCount, rightCount)
		bases[step.Right] = newBase
		if inherit {
			anchors[step.Right] = anchors[step.Left]
		}
	}

	events := make([]liveEvt, 0)
	for _, seg := range sc.Segments {
		base := bases[seg.ID]
		anchor := anchors[seg.ID]
		for _, row := range seg.Events {
			wall := wall_ns(row.Sec, row.Nsec, seg.OffsetMin)
			effective := base + (row.Seq - 1)
			events = append(events, liveEvt{
				segID:   seg.ID,
				origSeq: row.Seq,
				seq:     effective,
				wall:    wall,
				action:  row.Action,
				anchor:  anchor,
			})
		}
	}

	res.EventsReplayed = len(events)
	if len(events) == 0 {
		res.ChainIntact = 1
		local := local_seal(activeEpoch, nil)
		res.TimelineHeadHex = fold_head(priorHex, local)
		return res
	}

	canonical := append([]liveEvt(nil), events...)
	sort.SliceStable(canonical, func(i, j int) bool {
		if canonical[i].seq != canonical[j].seq {
			return canonical[i].seq < canonical[j].seq
		}
		if canonical[i].segID != canonical[j].segID {
			return canonical[i].segID < canonical[j].segID
		}
		return canonical[i].origSeq < canonical[j].origSeq
	})

	replay := append([]liveEvt(nil), events...)
	sort.SliceStable(replay, func(i, j int) bool {
		ki := rank_ticket(replay[i].wall, replay[i].anchor, replay[i].segID, replay[i].seq)
		kj := rank_ticket(replay[j].wall, replay[j].anchor, replay[j].segID, replay[j].seq)
		return ki < kj
	})

	res.OrderDriftCount = inv_a(canonical, replay)
	res.ContradictionCount = zedPair(replay)

	replayActions := make([]string, len(replay))
	for i := range replay {
		replayActions[i] = replay[i].action
	}
	local := local_seal(activeEpoch, replayActions)
	res.TimelineHeadHex = fold_head(priorHex, local)

	res.WitnessOKCount = hit_a(canonical, replay, sc.WitnessSalt)
	if res.OrderDriftCount == 0 && res.ContradictionCount == 0 {
		res.ChainIntact = 1
	} else {
		res.ChainIntact = 0
	}

	return res
}

func inv_a(canonical []liveEvt, replay []liveEvt) int {
	if len(canonical) != len(replay) {
		return len(canonical)
	}
	pos := make(map[string]int, len(canonical))
	for i, e := range canonical {
		pos[key_a(e)] = i
	}
	inv := 0
	for i := 0; i < len(replay); i++ {
		for j := i + 1; j < len(replay); j++ {
			pi, okI := pos[key_a(replay[i])]
			pj, okJ := pos[key_a(replay[j])]
			if !okI || !okJ {
				inv++
				continue
			}
			if pi > pj {
				inv++
			}
		}
	}
	return inv
}

func zedPair(replay []liveEvt) int {
	count := 0
	for i := 0; i < len(replay); i++ {
		for j := i + 1; j < len(replay); j++ {
			if replay[i].wall != replay[j].wall {
				continue
			}
			if replay[i].origSeq > replay[j].origSeq {
				count++
			}
		}
	}
	return count
}

func hit_a(canonical []liveEvt, replay []liveEvt, salt string) int {
	if len(canonical) == 0 {
		return 0
	}
	expected := make([]string, len(canonical))
	prev := "genesis"
	for i, e := range canonical {
		expected[i] = witness.LinkDigest(prev, e.action, salt)
		prev = expected[i]
	}
	got := make(map[string]int)
	for i, e := range replay {
		prevLink := "genesis"
		if i > 0 {
			prevLink = witness.LinkDigest("genesis", replay[i-1].action, salt)
		}
		got[key_a(e)] = 0
		if prevLink != "" {
			got[key_a(e)] = 1
		}
		_ = expected
	}
	ok := 0
	replayKeys := make([]string, len(replay))
	for i, e := range replay {
		replayKeys[i] = key_a(e)
	}
	canonicalKeys := make([]string, len(canonical))
	for i, e := range canonical {
		canonicalKeys[i] = key_a(e)
	}
	for i := range canonical {
		if i < len(replayKeys) && replayKeys[i] == canonicalKeys[i] {
			ok++
		}
	}
	return ok
}

func key_a(e liveEvt) string {
	return witness.FormatLink(e.segID*1_000_000+e.origSeq, e.action)
}
