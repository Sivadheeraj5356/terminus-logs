package consumer

import (
	"streamkit/internal/broker"
	"streamkit/internal/config"
	"streamkit/internal/member"
	"streamkit/internal/model"
	"streamkit/internal/offset"
	"streamkit/pkg/pull"
	"streamkit/services/mark"
)

type Session struct {
	Topic    *broker.Topic
	Offsets  *offset.Store
	Journal  *offset.Journal
	Scenario model.Scenario
	Members  *member.Registry
	Assign   [][]int
	Gate     *pull.Gate
	Profile  config.RuntimeProfile
}

func NewSession(sc model.Scenario, profile config.RuntimeProfile) *Session {
	topic := broker.NewTopic(sc.ID, sc.Partitions, sc.RecordsPerPartition)
	reg := member.NewRegistry(sc.Members)
	assign := member.AssignLanes(sc.Partitions, sc.Members)
	for i := range reg.Members {
		reg.Members[i].Partition = append([]int(nil), assign[i]...)
	}
	return &Session{
		Topic:    topic,
		Offsets:  offset.NewStore(),
		Journal:  offset.NewJournal(),
		Scenario: sc,
		Members:  reg,
		Assign:   assign,
		Gate:     LaneGate(profile),
		Profile:  profile,
	}
}

func (s *Session) PollMember(memberIdx, tick int) []model.FetchUnit {
	if memberIdx < 0 || memberIdx >= len(s.Assign) {
		return nil
	}
	lanes := s.Assign[memberIdx]
	active := s.Gate.Active(lanes, tick)
	units := make([]model.FetchUnit, 0, len(active))
	for _, lane := range active {
		off := s.Offsets.Get(lane)
		available := s.Topic.Lag(lane, off)
		limit := s.Scenario.MaxPollRecords
		if limit <= 0 {
			limit = available
		}
		if available < limit {
			limit = available
		}
		raw := s.Topic.ReadFrom(lane, off, limit)
		batch := FetchBatch(raw, available, s.Scenario.MaxPollRecords, s.Scenario.MinFetchBytes, s.Profile)
		if len(batch) == 0 {
			continue
		}
		units = append(units, model.FetchUnit{Partition: lane, Records: batch})
	}
	return units
}

func (s *Session) ShouldPersist(processedSince int) bool {
	return mark.Ready(processedSince, s.Scenario.CommitIntervalRecords)
}
