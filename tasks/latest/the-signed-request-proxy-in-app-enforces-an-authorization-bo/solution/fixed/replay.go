package spool

import (
	"encoding/hex"
	"os"

	"sigproxy/internal/audit"
	"sigproxy/internal/backend"
	"sigproxy/internal/config"
	"sigproxy/internal/semantics"
	"sigproxy/internal/trace"
)

type ReplayResult struct {
	RecordID  string
	Forwarded bool
	Reason    audit.ReasonCode
}

func ReplayPending(rt *config.Runtime, backendUnix string, traceW *trace.Writer, auditW *audit.SnapshotWriter, sealKeyHex string) ([]ReplayResult, error) {
	key, err := hex.DecodeString(sealKeyHex)
	if err != nil {
		key = []byte("demo-spool-seal-key-32-bytes!!")
	}
	pending, err := ListPending(rt.Config.SpoolDir)
	if err != nil {
		return nil, err
	}
	writer, _ := NewWriter(rt.Config.SpoolDir, sealKeyHex)
	var results []ReplayResult
	for _, rec := range pending {
		res := replayOne(rt, backendUnix, traceW, auditW, writer, rec, key)
		results = append(results, res)
	}
	return results, nil
}

func replayOne(rt *config.Runtime, backendUnix string, traceW *trace.Writer, auditW *audit.SnapshotWriter, writer *Writer, rec *Record, sealKey []byte) ReplayResult {
	if !VerifySeal(rec, sealKey) {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonIntegrityFailure}
	}

	key, ok := rt.Keyring.Lookup(rec.SemanticRequest.Tenant, rec.SemanticRequest.KeyID, rec.SemanticRequest.KeyEpoch)
	if !ok || key.Revoked {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonReplayQuarantine}
	}

	body, err := os.ReadFile(rec.BodyPath)
	if err != nil {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonIntegrityFailure}
	}

	sem := rec.SemanticRequest.Clone()
	sem.EntityBody = append([]byte(nil), body...)
	sem.EntityBodySHA256 = semantics.BodyDigest(body)
	sem.EntityBodyLength = len(body)

	rec.ReplayCount++
	fwd, err := backend.ForwardSemantic(backendUnix, sem)
	if err != nil {
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonReplayQuarantine}
	}

	rec.State = StateCompleted
	_ = writer.Update(rec)

	snap := audit.FromSemantic(sem, "spool", "allow", audit.ReasonAllow, rec.DecisionDigest, false)
	auditDigest, _ := auditW.WriteSnapshot(snap)
	traceW.AddFromSnapshot(snap, rec.WireDigest, len(sem.EntityBody), &trace.ForwardEvidence{
		BackendDigest:  fwd.BackendDigest,
		BackendLength:  fwd.BackendLength,
		Forwarded:      true,
		ResponseStatus: fwd.StatusCode,
	}, &trace.SpoolEvidence{
		RecordID:    rec.RecordID,
		State:       string(rec.State),
		ReplayCount: rec.ReplayCount,
		SealValid:   true,
	}, auditDigest)

	return ReplayResult{RecordID: rec.RecordID, Forwarded: true, Reason: audit.ReasonAllow}
}
