package audit

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"

	"chainaudit/internal/canon"
	"chainaudit/internal/kms"
	"chainaudit/internal/merkle"
	"chainaudit/internal/model"
)

// VerifyStream recomputes a stream's chain state from its current rows and
// classifies it: for each checkpoint, the Merkle root is rebuilt from the
// batch's stored leaf hashes and compared against the checkpoint's claimed
// root, and the checkpoint's signature is re-verified against the signing
// key.
func VerifyStream(ctx context.Context, kmsClient *kms.Client, stream *model.Stream, events []model.Event, checkpoints []model.Checkpoint) StreamVerifyReport {
	report := StreamVerifyReport{
		StreamID:        stream.StreamID,
		EventCount:      len(events),
		CheckpointCount: len(checkpoints),
		RevokedKeyIDs:   []string{},
	}

	eventsBySeq := make(map[int64]*model.Event, len(events))
	for i := range events {
		eventsBySeq[events[i].Seq] = &events[i]
	}

	var (
		corrupt       bool
		reason        string
		firstBadBatch *int64
	)

	tip := merkle.Genesis(stream.StreamID)
	for _, cp := range checkpoints {
		leaves, haveAllLeaves := gatherLeaves(eventsBySeq, cp.StartSeq, cp.EndSeq)
		if haveAllLeaves {
			var claimedRoot [32]byte
			copy(claimedRoot[:], cp.MerkleRoot)
			if merkle.Root(leaves) != claimedRoot {
				corrupt = true
				reason = "tampered_merkle_root"
				b := cp.BatchIndex
				if firstBadBatch == nil || b < *firstBadBatch {
					firstBadBatch = &b
				}
			}
		}

		key, err := kmsClient.FetchKey(ctx, cp.KeyID)
		if err != nil {
			corrupt = true
			reason = "kms_unavailable"
		} else {
			var claimedRoot [32]byte
			copy(claimedRoot[:], cp.MerkleRoot)
			signingBytes := canon.CheckpointSigningBytes(stream.StreamID, cp.BatchIndex, cp.StartSeq, cp.EndSeq, claimedRoot)
			mac := hmac.New(sha256.New, key.Material)
			mac.Write(signingBytes)
			expected := mac.Sum(nil)
			if !hmac.Equal(expected, cp.Signature) {
				corrupt = true
				reason = "tampered_checkpoint_signature"
				b := cp.BatchIndex
				if firstBadBatch == nil || b < *firstBadBatch {
					firstBadBatch = &b
				}
			}
		}

		var root [32]byte
		copy(root[:], cp.MerkleRoot)
		tip = merkle.FoldCheckpoint(tip, cp.BatchIndex, cp.StartSeq, cp.EndSeq, root, cp.KeyID)
	}

	report.ChainTipHash = hex.EncodeToString(tip[:])
	report.FirstBadBatch = firstBadBatch

	if corrupt {
		report.Status = "corrupt"
		report.Reason = &reason
	} else {
		report.Status = "ok"
	}

	return report
}

// gatherLeaves collects the leaf hashes covering [start, end]. Erased
// (tombstoned) rows keep their place in the log but carry no payload of
// their own anymore, so they're skipped here the same way a physically
// absent row would be; ok is false only when the batch can't be reconstructed
// at all (already pruned).
func gatherLeaves(bySeq map[int64]*model.Event, start, end int64) ([][32]byte, bool) {
	leaves := make([][32]byte, 0, end-start+1)
	for seq := start; seq <= end; seq++ {
		ev, ok := bySeq[seq]
		if !ok {
			return nil, false
		}
		if ev.Tombstone {
			continue
		}
		var lh [32]byte
		copy(lh[:], ev.LeafHash)
		leaves = append(leaves, lh)
	}
	return leaves, true
}
