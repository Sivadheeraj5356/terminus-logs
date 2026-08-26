package internal

import (
	"context"
	"fmt"

	"s8lab/j2"
	"s8lab/k5"
	"s8lab/m4"
)

func ProcessFixture(label string, entries *[]RunEntry) error {
	doc, err := LoadPersist()
	if err != nil {
		return err
	}
	head, ok := RowForLabel(doc, label)
	if !ok {
		return fmt.Errorf("missing ledger row for %s", label)
	}
	streamRows, segments, err := LoadStream(label)
	if err != nil {
		return err
	}
	pending := PendingRev(streamRows)
	rev, err := m4.TrackRev(head.Era, pending)
	if err != nil {
		return err
	}
	store := Store{
		Rev:       rev,
		AttachID:  head.AttachID,
		Track:     head.Track,
		HardLimit: head.HardLimit,
	}
	snap := Snapshot{Rev: pending, AttachID: head.AttachID, HardLimit: head.HardLimit}
	if err := j2.CommitStore(&store, snap, 0); err != nil {
		return err
	}
	replayed, err := k5.ReplaySegments(segments)
	if err != nil {
		return err
	}
	attach := head.AttachID
	track := head.Track
	limit := head.HardLimit
	for _, seg := range replayed {
		if seg.Era <= store.Rev {
			attach = seg.AttachID
			track = seg.Track
			if seg.HardLimit > 0 {
				limit = seg.HardLimit
			}
		}
		*entries = append(*entries, RunEntry{
			TMs:       0,
			RunLabel:  label,
			Phase:     "apply",
			SegmentID: seg.SegmentID,
			Era:       seg.Era,
			AttachID:  seg.AttachID,
			Outcome:   "applied",
		})
	}
	attach = m4.MatrixAttach(label, attach)
	for i := range doc.Rows {
		if doc.Rows[i].RunLabel == label {
			doc.Rows[i].Era = store.Rev
			doc.Rows[i].AttachID = attach
			doc.Rows[i].Track = track
			if !doc.Rows[i].Retired {
				doc.Rows[i].HardLimit = limit
			}
		}
	}
	if err := SavePersist(doc); err != nil {
		return err
	}
	*entries = append(*entries, RunEntry{
		TMs:       0,
		RunLabel:  label,
		Phase:     "head",
		SegmentID: "-",
		Era:       store.Rev,
		AttachID:  attach,
		Outcome:   "set",
	})
	return nil
}

func ListLimits(ctx context.Context, boot int) ([]PersistRow, error) {
	_ = ctx
	doc, err := LoadPersist()
	if err != nil {
		return nil, err
	}
	rows := make([]PersistRow, len(doc.Rows))
	copy(rows, doc.Rows)
	if boot < 2 {
		return rows, nil
	}
	tail, err := LoadJournalTail()
	if err != nil || len(tail) == 0 {
		return rows, nil
	}
	byLabel := map[string]int{}
	for i, row := range rows {
		byLabel[row.RunLabel] = i
	}
	for _, seg := range tail {
		label := seg.RunLabel
		if label == "" && len(seg.SegmentID) >= 3 {
			label = seg.SegmentID[:3]
		}
		idx, ok := byLabel[label]
		if !ok {
			continue
		}
		if seg.Kind == "tombstone" || seg.Kind == "commit" {
			if seg.HardLimit > 0 {
				rows[idx].HardLimit = seg.HardLimit
			}
			if seg.AttachID != "" {
				rows[idx].AttachID = seg.AttachID
			}
			if seg.Era > 0 {
				rows[idx].Era = seg.Era
			}
		}
	}
	return rows, nil
}
