package audit

import (
	"encoding/hex"

	"chainaudit/internal/merkle"
	"chainaudit/internal/model"
)

const (
	defaultRetentionDays int64 = 90
	secondsPerDay         int64 = 86400
)

// deleter is the subset of store.Store that CompactStream needs.
type deleter interface {
	DeleteBatch(streamID string, startSeq, endSeq int64) (int64, error)
}

// CompactStream prunes events past the retention window, one event at a
// time, and reports what it removed.
func CompactStream(store deleter, stream *model.Stream, events []model.Event, checkpoints []model.Checkpoint, now int64) (StreamCompactManifest, error) {
	manifest := StreamCompactManifest{
		StreamID:        stream.StreamID,
		BatchesPruned:   []int64{},
		BatchesRetained: []int64{},
	}

	cutoff := now - defaultRetentionDays*secondsPerDay

	tip := merkle.Genesis(stream.StreamID)
	for _, cp := range checkpoints {
		var root [32]byte
		copy(root[:], cp.MerkleRoot)
		tip = merkle.FoldCheckpoint(tip, cp.BatchIndex, cp.StartSeq, cp.EndSeq, root, cp.KeyID)
	}
	manifest.ChainTipHash = hex.EncodeToString(tip[:])

	for _, ev := range events {
		if ev.Ts > cutoff {
			continue
		}
		if ev.LegalHold {
			continue
		}
		deleted, err := store.DeleteBatch(stream.StreamID, ev.Seq, ev.Seq)
		if err != nil {
			return manifest, err
		}
		if deleted > 0 {
			manifest.EventsDeleted += deleted
		}
	}

	return manifest, nil
}
