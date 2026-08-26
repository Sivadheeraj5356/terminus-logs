#!/bin/bash
set -euo pipefail

cd /app

cat > internal/audit/verify.go <<'CHAINAUDIT_GOLDEN_EOF'
package audit

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"sort"

	"chainaudit/internal/canon"
	"chainaudit/internal/kms"
	"chainaudit/internal/merkle"
	"chainaudit/internal/model"
)

// Precedence order for a stream's single reported reason when more than one
// finding coexists (CHAINAUDIT-SPEC.md Section 8.7). Lower number wins.
const (
	priorityTamperedEvent      = 1
	priorityTamperedMerkleRoot = 2
	priorityTamperedSignature  = 3
	priorityRevokedKey         = 4
	priorityKMSUnavailable     = 5
	priorityNone               = 6
)

var reasonForPriority = map[int]string{
	priorityTamperedEvent:      "tampered_event",
	priorityTamperedMerkleRoot: "tampered_merkle_root",
	priorityTamperedSignature:  "tampered_checkpoint_signature",
	priorityRevokedKey:         "revoked_key",
	priorityKMSUnavailable:     "kms_unavailable",
}

// VerifyStream recomputes a stream's chain state from its current rows and
// classifies it. Every event currently in the table -- checkpointed or still
// in the uncheckpointed tail -- gets its stored leaf_hash re-derived from its
// current content; a mismatch means the row changed after it was hashed.
// Every checkpoint additionally gets its Merkle root rebuilt from the stored
// leaf hashes of its batch (skipped for a batch that has already been pruned:
// that is what checkpointing is for) and its signature re-verified against
// the KMS key it claims to have been signed with. A revoked key does not by
// itself make a stream corrupt -- it makes the checkpoints signed with that
// key unverifiable -- but content and structural checks still run regardless
// of key status, so a stream can't hide real tampering behind a revoked key.
//
// A stream can trip more than one of these findings at once, so the single
// reported reason follows the fixed precedence in Section 8.7: only a
// strictly higher-priority finding is allowed to overwrite the one already
// recorded, never a same-or-lower one, regardless of the order checks happen
// to run in.
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

	best := priorityNone
	consider := func(p int) {
		if p < best {
			best = p
		}
	}

	var (
		firstBadSeq   *int64
		firstBadBatch *int64
		revokedSeen   = map[string]bool{}
	)

	for i := range events {
		ev := &events[i]
		got := merkle.LeafHash(canon.Event(stream, ev))
		if !bytes.Equal(got[:], ev.LeafHash) {
			consider(priorityTamperedEvent)
			seq := ev.Seq
			if firstBadSeq == nil || seq < *firstBadSeq {
				firstBadSeq = &seq
			}
		}
	}

	tip := merkle.Genesis(stream.StreamID)
	for _, cp := range checkpoints {
		leaves, haveAllLeaves := gatherLeaves(eventsBySeq, cp.StartSeq, cp.EndSeq)
		if haveAllLeaves {
			var claimedRoot [32]byte
			copy(claimedRoot[:], cp.MerkleRoot)
			if merkle.Root(leaves) != claimedRoot {
				consider(priorityTamperedMerkleRoot)
				b := cp.BatchIndex
				if firstBadBatch == nil || b < *firstBadBatch {
					firstBadBatch = &b
				}
			}
		}

		key, err := kmsClient.FetchKey(ctx, cp.KeyID)
		if err != nil {
			consider(priorityKMSUnavailable)
		} else if key.Status == kms.KeyRevoked {
			consider(priorityRevokedKey)
			if !revokedSeen[cp.KeyID] {
				revokedSeen[cp.KeyID] = true
				report.RevokedKeyIDs = append(report.RevokedKeyIDs, cp.KeyID)
			}
		} else {
			var claimedRoot [32]byte
			copy(claimedRoot[:], cp.MerkleRoot)
			signingBytes := canon.CheckpointSigningBytes(stream.StreamID, cp.BatchIndex, cp.StartSeq, cp.EndSeq, claimedRoot)
			mac := hmac.New(sha256.New, key.Material)
			mac.Write(signingBytes)
			expected := mac.Sum(nil)
			if !hmac.Equal(expected, cp.Signature) {
				consider(priorityTamperedSignature)
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

	sort.Strings(report.RevokedKeyIDs)

	report.ChainTipHash = hex.EncodeToString(tip[:])
	report.FirstBadSeq = firstBadSeq
	report.FirstBadBatch = firstBadBatch

	switch {
	case best <= priorityTamperedSignature:
		report.Status = "corrupt"
		r := reasonForPriority[best]
		report.Reason = &r
	case best <= priorityKMSUnavailable:
		report.Status = "legacy_unverifiable"
		r := reasonForPriority[best]
		report.Reason = &r
	default:
		report.Status = "ok"
	}

	return report
}

func gatherLeaves(bySeq map[int64]*model.Event, start, end int64) ([][32]byte, bool) {
	leaves := make([][32]byte, 0, end-start+1)
	for seq := start; seq <= end; seq++ {
		ev, ok := bySeq[seq]
		if !ok {
			return nil, false
		}
		var lh [32]byte
		copy(lh[:], ev.LeafHash)
		leaves = append(leaves, lh)
	}
	return leaves, true
}
CHAINAUDIT_GOLDEN_EOF

cat > internal/audit/compact.go <<'CHAINAUDIT_GOLDEN_EOF'
package audit

import (
	"encoding/hex"

	"chainaudit/internal/merkle"
	"chainaudit/internal/model"
)

const SecondsPerDay int64 = 86400

// deleter is the subset of store.Store that CompactStream needs, so callers
// can pass a *store.Store without an import cycle and tests can pass a fake.
type deleter interface {
	DeleteBatch(streamID string, startSeq, endSeq int64) (int64, error)
}

// CompactStream prunes the events belonging to a stream's expired checkpoint
// batches. Pruning is only ever whole-batch: a batch is eligible only when
// every event still present in it is both past retention and free of
// per-event legal hold, and a whole-stream legal hold blocks every batch
// regardless of age. This is what keeps a pruned stream re-verifiable
// afterward -- the checkpoint that covered a deleted batch is never touched,
// so its signed Merkle root still stands in for the rows that are gone.
// Running twice with the same now is a no-op the second time: a batch with no
// events left in it (already pruned) is skipped rather than re-processed.
func CompactStream(store deleter, stream *model.Stream, events []model.Event, checkpoints []model.Checkpoint, now int64) (StreamCompactManifest, error) {
	manifest := StreamCompactManifest{
		StreamID:        stream.StreamID,
		BatchesPruned:   []int64{},
		BatchesRetained: []int64{},
	}

	eventsBySeq := make(map[int64]*model.Event, len(events))
	for i := range events {
		eventsBySeq[events[i].Seq] = &events[i]
	}

	cutoff := now - stream.RetentionDays*SecondsPerDay

	tip := merkle.Genesis(stream.StreamID)
	for _, cp := range checkpoints {
		var root [32]byte
		copy(root[:], cp.MerkleRoot)
		tip = merkle.FoldCheckpoint(tip, cp.BatchIndex, cp.StartSeq, cp.EndSeq, root, cp.KeyID)

		if stream.LegalHold {
			manifest.BatchesRetained = append(manifest.BatchesRetained, cp.BatchIndex)
			continue
		}

		anyRemaining := false
		eligible := true
		for seq := cp.StartSeq; seq <= cp.EndSeq; seq++ {
			ev, ok := eventsBySeq[seq]
			if !ok {
				continue // already pruned by an earlier run
			}
			anyRemaining = true
			if ev.LegalHold || ev.Ts > cutoff {
				eligible = false
				break
			}
		}

		if !anyRemaining {
			continue // idempotent: nothing left to prune in this batch
		}
		if !eligible {
			manifest.BatchesRetained = append(manifest.BatchesRetained, cp.BatchIndex)
			continue
		}

		deleted, err := store.DeleteBatch(stream.StreamID, cp.StartSeq, cp.EndSeq)
		if err != nil {
			return manifest, err
		}
		manifest.BatchesPruned = append(manifest.BatchesPruned, cp.BatchIndex)
		manifest.EventsDeleted += deleted
	}

	manifest.ChainTipHash = hex.EncodeToString(tip[:])
	return manifest, nil
}
CHAINAUDIT_GOLDEN_EOF

go build -mod=vendor -o /usr/local/bin/chainaudit ./cmd/chainaudit

mkdir -p /app/out

# Proof-of-concept: construct a layered-evasion tamper against a copy of the
# database (never the original) -- change one clean event's content and
# patch its own stored leaf_hash to match, the way an attacker with database
# write access but no signing key could. That defeats the per-event content
# check on its own, but not the checkpoint's Merkle root, which still covers
# the batch as a whole and can't be forged without the key.
mkdir -p /app/cmd/craftexploit
cat > /app/cmd/craftexploit/main.go <<'CHAINAUDIT_EXPLOIT_EOF'
package main

import (
	"database/sql"
	"encoding/json"
	"flag"
	"log"
	"os"

	_ "modernc.org/sqlite"

	"chainaudit/internal/canon"
	"chainaudit/internal/merkle"
	"chainaudit/internal/model"
)

func main() {
	dbPath := flag.String("db", "", "path to the exploit db copy")
	reportPath := flag.String("report", "", "path to write exploit_report.json")
	streamID := flag.String("stream", "", "target stream id")
	seq := flag.Int64("seq", 0, "target seq")
	flag.Parse()

	db, err := sql.Open("sqlite", *dbPath)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	var migratedAt sql.NullInt64
	if err := db.QueryRow("SELECT migrated_at FROM streams WHERE stream_id=?", *streamID).Scan(&migratedAt); err != nil {
		log.Fatal(err)
	}
	stream := &model.Stream{StreamID: *streamID}
	if migratedAt.Valid {
		v := migratedAt.Int64
		stream.MigratedAt = &v
	}

	var ts int64
	var eventType string
	var payload []byte
	var tombstone, legalHold int64
	row := db.QueryRow("SELECT ts, event_type, payload, tombstone, legal_hold FROM events WHERE stream_id=? AND seq=?", *streamID, *seq)
	if err := row.Scan(&ts, &eventType, &payload, &tombstone, &legalHold); err != nil {
		log.Fatal(err)
	}

	newPayload := append(append([]byte{}, payload...), []byte(`,"tampered":true`)...)

	ev := &model.Event{
		StreamID: *streamID, Seq: *seq, Ts: ts, EventType: eventType,
		Payload: newPayload, Tombstone: tombstone != 0, LegalHold: legalHold != 0,
	}
	newLeaf := merkle.LeafHash(canon.Event(stream, ev))

	if _, err := db.Exec("UPDATE events SET payload=?, leaf_hash=? WHERE stream_id=? AND seq=?",
		newPayload, newLeaf[:], *streamID, *seq); err != nil {
		log.Fatal(err)
	}

	report, _ := json.MarshalIndent(map[string]interface{}{
		"stream_id": *streamID,
		"seq":       *seq,
	}, "", "  ")
	if err := os.WriteFile(*reportPath, report, 0644); err != nil {
		log.Fatal(err)
	}
}
CHAINAUDIT_EXPLOIT_EOF

go build -mod=vendor -o /tmp/craftexploit ./cmd/craftexploit
cp /app/data/chainaudit.db /app/out/exploit.db
/tmp/craftexploit -db /app/out/exploit.db -report /app/out/exploit_report.json -stream untouched-002 -seq 5
rm -rf /app/cmd/craftexploit

/usr/local/bin/chainaudit verify --db /app/data/chainaudit.db --out /app/out/verify_report.json --kms-addr http://127.0.0.1:8500
/usr/local/bin/chainaudit compact --db /app/data/chainaudit.db --out /app/out/compact_manifest.json --now-file /app/data/NOW.txt
/usr/local/bin/chainaudit verify --db /app/data/chainaudit.db --out /app/out/verify_report.json --kms-addr http://127.0.0.1:8500
