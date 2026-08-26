package ledger

import (
	"sort"

	"github.com/terminus/hopledger/checkpoint"
	"github.com/terminus/hopledger/emit"
	"github.com/terminus/hopledger/ingest"
	"github.com/terminus/hopledger/policy"
	"github.com/terminus/hopledger/state"
)

type counts struct {
	appliedEvents      int
	cancelledEvents    int
	supersededEvents   int
	duplicateRawEvents int
	suppressedHops     int
}

type engine struct {
	records        []ingest.Record
	winners        map[ingest.IdentityKey]ingest.Record
	links          map[string]*state.Link
	audit          []emit.AuditEntry
	counts         counts
	activePolicy   *policy.Document
	policyUpdates  []map[string]interface{}
	processedKeys  map[ingest.IdentityKey]struct{}
	lineCursors    map[string]int
	maxEpoch       int
	rawInputDigest string
	initialPolicy  *policy.Document
	policyDigest   string
	checkpointDir  string
}

func Replay(
	records []ingest.Record,
	winners map[ingest.IdentityKey]ingest.Record,
	rawInputDigest string,
	initialPolicy *policy.Document,
	policyDigest string,
	checkpointDir string,
) (*emit.Report, []emit.AuditEntry, error) {
	e := &engine{
		records:        records,
		winners:        winners,
		links:          make(map[string]*state.Link),
		activePolicy:   initialPolicy,
		processedKeys:  make(map[ingest.IdentityKey]struct{}),
		lineCursors:    make(map[string]int),
		rawInputDigest: rawInputDigest,
		initialPolicy:  initialPolicy,
		policyDigest:   policyDigest,
		checkpointDir:  checkpointDir,
	}
	for _, rec := range records {
		if err := e.process(rec); err != nil {
			return nil, nil, err
		}
	}
	return e.buildReport(), e.audit, nil
}

func ValidateResume(snap *checkpoint.Snapshot, rawInputDigest string, records []ingest.Record) error {
	if snap.RawInputDigest != "" && snap.RawInputDigest != rawInputDigest {
		return errStale("raw input digest mismatch")
	}
	for _, rec := range records {
		if rec.Epoch < snap.Epoch {
			return errStale("stale epoch event")
		}
	}
	return nil
}

type staleError string

func (e staleError) Error() string { return string(e) }

func errStale(msg string) error { return staleError(msg) }

func IsStale(err error) bool {
	_, ok := err.(staleError)
	return ok
}

func (e *engine) linkRow(linkID string) *state.Link {
	st, ok := e.links[linkID]
	if !ok {
		st = state.NewLink()
		st.SLAMs = policy.SLA(e.activePolicy, linkID)
		e.links[linkID] = st
	}
	return st
}

func (e *engine) touch(rec ingest.Record, linkID string) {
	st := e.linkRow(linkID)
	st.Referenced = true
	st.LastEpoch = rec.Epoch
	st.LastSeq = rec.Seq
	st.SLAMs = policy.SLA(e.activePolicy, linkID)
}

func (e *engine) auditAdd(rec ingest.Record, decision, reason, link string) {
	if link == "" {
		link = rec.Link
	}
	e.audit = append(e.audit, emit.AuditEntry{
		Decision: decision,
		Epoch:    rec.Epoch,
		Seq:      rec.Seq,
		Lane:     rec.Raw.Lane,
		Source:   rec.Source,
		OpID:     rec.OpID,
		Rev:      rec.Rev,
		Kind:     rec.Kind,
		Reason:   reason,
		Link:     link,
	})
}

func bucketIndex(ms int) int {
	b := ms / 50
	if b > 5 {
		return 5
	}
	return b
}

func (e *engine) process(rec ingest.Record) error {
	key := ingest.Identity(rec)
	winner := e.winners[key]

	if rec.MergeIndex != winner.MergeIndex {
		if rec.Rev < winner.Rev {
			e.auditAdd(rec, "superseded", "lower_rev", "")
			e.counts.supersededEvents++
		} else if rec.Raw.RawHash == winner.Raw.RawHash {
			e.auditAdd(rec, "duplicate_raw", "exact_raw_duplicate", "")
			e.counts.duplicateRawEvents++
		} else {
			e.auditAdd(rec, "superseded", "tie_break", "")
			e.counts.supersededEvents++
		}
		return nil
	}

	if rec.Cancel {
		e.auditAdd(rec, "cancelled", "tombstone", "")
		e.counts.cancelledEvents++
		e.processedKeys[key] = struct{}{}
		if rec.Link != "" {
			e.touch(rec, rec.Link)
		}
		if rec.Epoch > e.maxEpoch {
			e.maxEpoch = rec.Epoch
		}
		return nil
	}

	if rec.Kind == "note" {
		e.auditAdd(rec, "note", "ignored", "")
		e.processedKeys[key] = struct{}{}
		if rec.Epoch > e.maxEpoch {
			e.maxEpoch = rec.Epoch
		}
		return nil
	}

	if rec.Kind == "policy_update" {
		doc := policy.FromMap(rec.Policy)
		e.activePolicy = &doc
		e.policyUpdates = append(e.policyUpdates, rec.Policy)
		e.auditAdd(rec, "policy_update", "applied", "")
		e.counts.appliedEvents++
		e.processedKeys[key] = struct{}{}
		if rec.Epoch > e.maxEpoch {
			e.maxEpoch = rec.Epoch
		}
		return nil
	}

	if rec.Kind == "checkpoint" {
		e.auditAdd(rec, "checkpoint", rec.Tag, "")
		e.counts.appliedEvents++
		e.processedKeys[key] = struct{}{}
		for _, r := range e.records {
			if r.MergeIndex <= rec.MergeIndex {
				prev := e.lineCursors[r.Raw.Lane]
				if r.Raw.LineNum > prev {
					e.lineCursors[r.Raw.Lane] = r.Raw.LineNum
				}
			}
		}
		if err := e.writeCheckpoint(rec); err != nil {
			return err
		}
		if rec.Epoch > e.maxEpoch {
			e.maxEpoch = rec.Epoch
		}
		return nil
	}

	if rec.Link != "" {
		e.touch(rec, rec.Link)
	}

	switch rec.Kind {
	case "link_open":
		st := e.linkRow(rec.Link)
		st.Open = true
		e.auditAdd(rec, "applied", "open", "")
		e.counts.appliedEvents++
	case "link_close":
		st := e.linkRow(rec.Link)
		if st.Open {
			st.Open = false
			e.auditAdd(rec, "applied", "close", "")
			e.counts.appliedEvents++
		} else {
			e.auditAdd(rec, "noop", "noop_close", "")
		}
	case "quarantine":
		st := e.linkRow(rec.Link)
		st.Quarantined = true
		e.auditAdd(rec, "applied", "quarantine", "")
		e.counts.appliedEvents++
	case "clear_quarantine":
		st := e.linkRow(rec.Link)
		if st.Quarantined {
			st.Quarantined = false
			e.auditAdd(rec, "applied", "clear", "")
			e.counts.appliedEvents++
		} else {
			e.auditAdd(rec, "noop", "noop_clear_quarantine", "")
		}
	case "hop":
		st := e.linkRow(rec.Link)
		if !st.Open {
			e.auditAdd(rec, "suppressed", "closed", "")
			e.counts.suppressedHops++
		} else if st.Quarantined {
			e.auditAdd(rec, "suppressed", "quarantined", "")
			e.counts.suppressedHops++
		} else {
			ms := rec.Ms
			st.HopCount++
			st.SumMs += ms
			if ms > st.MaxMs {
				st.MaxMs = ms
			}
			if st.SLAMs > 0 && ms > st.SLAMs {
				st.AlarmBreaches++
			}
			st.Buckets[bucketIndex(ms)]++
			e.auditAdd(rec, "applied", "hop", "")
			e.counts.appliedEvents++
		}
	}

	e.processedKeys[key] = struct{}{}
	if rec.Epoch > e.maxEpoch {
		e.maxEpoch = rec.Epoch
	}
	return nil
}

func (e *engine) writeCheckpoint(rec ingest.Record) error {
	links := make(map[string]state.Link)
	for lid, st := range e.links {
		if !st.Referenced {
			continue
		}
		links[lid] = *st
	}
	winnerKeys := make([][]interface{}, 0, len(e.processedKeys))
	for k := range e.processedKeys {
		winnerKeys = append(winnerKeys, []interface{}{k.Epoch, k.Seq, k.Source, k.OpID})
	}
	var policyState interface{}
	if e.activePolicy != nil {
		policyState = e.activePolicy
	}
	snap := checkpoint.Snapshot{
		SchemaVersion: 3,
		Epoch:         rec.Epoch,
		NextSeq:       rec.Seq + 1,
		AppliedEvents: e.counts.appliedEvents,
		AuditCounts: checkpoint.AuditCounts{
			CancelledEvents:    e.counts.cancelledEvents,
			SupersededEvents:   e.counts.supersededEvents,
			DuplicateRawEvents: e.counts.duplicateRawEvents,
			SuppressedHops:     e.counts.suppressedHops,
		},
		PolicyState:         policyState,
		PolicyUpdates:       append([]map[string]interface{}(nil), e.policyUpdates...),
		PolicyLineageDigest: policy.LineageDigest(e.initialPolicy, e.policyUpdates),
		Links:               links,
		WinnerKeys:          winnerKeys,
		LineCursors:         copyLineCursors(e.lineCursors),
		RawInputDigest:      e.rawInputDigest,
	}
	return checkpoint.Write(e.checkpointDir, rec.Tag, snap)
}

func copyLineCursors(m map[string]int) map[string]int {
	out := make(map[string]int, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}

func (e *engine) buildReport() *emit.Report {
	rows := make([]emit.LinkRow, 0)
	openCount := 0
	quarantinedCount := 0
	alarmTotal := 0
	for linkID, st := range e.links {
		if !st.Referenced {
			continue
		}
		if st.Open {
			openCount++
		}
		if st.Quarantined {
			quarantinedCount++
		}
		alarmTotal += st.AlarmBreaches
		rows = append(rows, emit.LinkRow{
			LinkID:        linkID,
			Open:          st.Open,
			Quarantined:   st.Quarantined,
			HopCount:      st.HopCount,
			SumMs:         st.SumMs,
			MaxMs:         st.MaxMs,
			AlarmBreaches: st.AlarmBreaches,
			SLAMs:         st.SLAMs,
			Buckets:       append([]int(nil), st.Buckets...),
			LastEpoch:     st.LastEpoch,
			LastSeq:       st.LastSeq,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		return rows[i].LinkID < rows[j].LinkID
	})
	lineage := policy.LineageDigest(e.initialPolicy, e.policyUpdates)
	epochsSeen := e.maxEpoch + 1
	if epochsSeen < 0 {
		epochsSeen = 0
	}
	return &emit.Report{
		SchemaVersion:       3,
		EpochsSeen:          epochsSeen,
		AppliedEvents:       e.counts.appliedEvents,
		CancelledEvents:     e.counts.cancelledEvents,
		SupersededEvents:    e.counts.supersededEvents,
		DuplicateRawEvents:  e.counts.duplicateRawEvents,
		SuppressedHops:      e.counts.suppressedHops,
		OpenLinkCount:       openCount,
		QuarantinedCount:    quarantinedCount,
		AlarmBreachTotal:    alarmTotal,
		PolicyDigest:        e.policyDigest,
		PolicyLineageDigest: lineage,
		RawInputDigest:      e.rawInputDigest,
		Links:               rows,
	}
}
